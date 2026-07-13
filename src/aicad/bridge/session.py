from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import stat
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from platformdirs import user_runtime_dir

from aicad.bridge.protocol import PROTOCOL_VERSION
from aicad.bridge.transport import BridgeEndpoint


SESSION_FILE_NAME = "bridge-session.json"
MAX_SESSION_FILE_BYTES = 16 * 1024


class BridgeSessionError(RuntimeError):
    """Raised when local bridge discovery state is missing or unsafe."""


class BridgeSessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[PROTOCOL_VERSION] = PROTOCOL_VERSION
    session_id: UUID
    host: str
    port: int
    session_token: str = Field(min_length=32, max_length=256, repr=False)
    process_id: int = Field(gt=0)
    started_at: datetime

    @model_validator(mode="after")
    def validate_endpoint_and_timestamp(self) -> BridgeSessionRecord:
        BridgeEndpoint(self.host, self.port, self.session_token)
        if self.started_at.utcoffset() is None:
            raise ValueError("The bridge session timestamp must include a timezone.")
        return self

    @property
    def endpoint(self) -> BridgeEndpoint:
        return BridgeEndpoint(self.host, self.port, self.session_token)


class BridgeSessionStore:
    """Publish and discover one authenticated GUI bridge session atomically."""

    def __init__(self, runtime_directory: str | os.PathLike[str]) -> None:
        self._runtime_directory = Path(runtime_directory).absolute()
        self._session_file = self._runtime_directory / SESSION_FILE_NAME

    @property
    def path(self) -> Path:
        return self._session_file

    def publish(
        self,
        endpoint: BridgeEndpoint,
        *,
        process_id: int | None = None,
        session_id: UUID | None = None,
    ) -> BridgeSessionRecord:
        record = BridgeSessionRecord(
            session_id=session_id or uuid4(),
            host=endpoint.host,
            port=endpoint.port,
            session_token=endpoint.session_token,
            process_id=process_id if process_id is not None else os.getpid(),
            started_at=datetime.now(timezone.utc),
        )
        self._prepare_runtime_directory()
        self._reject_symlink(self._session_file)

        encoded = (record.model_dump_json(indent=2) + "\n").encode("utf-8")
        if len(encoded) > MAX_SESSION_FILE_BYTES:
            raise BridgeSessionError("The bridge session record is unexpectedly large.")

        temporary = self._runtime_directory / (
            f".{SESSION_FILE_NAME}.{secrets.token_hex(8)}.tmp"
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = None
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._session_file)
            self._restrict_file_permissions(self._session_file)
        except OSError as exc:
            raise BridgeSessionError(
                "The bridge session record could not be published."
            ) from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        return record

    def load(self) -> BridgeSessionRecord:
        self._prepare_runtime_directory(create=False)
        return self._load_path(self._session_file)

    def clear(self, session_id: UUID) -> bool:
        """Remove only the matching record without deleting a newer session."""

        self._prepare_runtime_directory(create=False)
        self._reject_symlink(self._session_file)
        if not self._session_file.exists():
            return False

        tombstone = self._runtime_directory / (
            f".{SESSION_FILE_NAME}.{secrets.token_hex(8)}.closing"
        )
        try:
            os.replace(self._session_file, tombstone)
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise BridgeSessionError(
                "The bridge session record could not be claimed for cleanup."
            ) from exc

        try:
            record = self._load_path(tombstone)
            if record.session_id == session_id:
                tombstone.unlink(missing_ok=True)
                return True
            if not self._session_file.exists():
                os.replace(tombstone, self._session_file)
            else:
                tombstone.unlink(missing_ok=True)
            return False
        except Exception:
            if tombstone.exists() and not self._session_file.exists():
                try:
                    os.replace(tombstone, self._session_file)
                except OSError:
                    pass
            raise

    def _prepare_runtime_directory(self, *, create: bool = True) -> None:
        if self._runtime_directory.is_symlink():
            raise BridgeSessionError("The bridge runtime directory cannot be a symlink.")
        try:
            if create:
                self._runtime_directory.mkdir(parents=True, exist_ok=True)
            elif not self._runtime_directory.is_dir():
                raise BridgeSessionError("No bridge runtime directory is available.")
        except OSError as exc:
            raise BridgeSessionError(
                "The bridge runtime directory is not available."
            ) from exc
        if not self._runtime_directory.is_dir():
            raise BridgeSessionError("The bridge runtime path is not a directory.")

    @staticmethod
    def _reject_symlink(path: Path) -> None:
        if path.is_symlink():
            raise BridgeSessionError("The bridge session file cannot be a symlink.")

    @staticmethod
    def _restrict_file_permissions(path: Path) -> None:
        try:
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError as exc:
            raise BridgeSessionError(
                "The bridge session file permissions could not be restricted."
            ) from exc

    @staticmethod
    def _load_path(path: Path) -> BridgeSessionRecord:
        if path.is_symlink():
            raise BridgeSessionError("The bridge session file cannot be a symlink.")
        try:
            file_size = path.stat().st_size
            if file_size == 0 or file_size > MAX_SESSION_FILE_BYTES:
                raise BridgeSessionError("The bridge session record size is invalid.")
            encoded = path.read_bytes()
            return BridgeSessionRecord.model_validate_json(encoded)
        except BridgeSessionError:
            raise
        except FileNotFoundError as exc:
            raise BridgeSessionError("No active GUI bridge session was found.") from exc
        except (OSError, ValidationError) as exc:
            raise BridgeSessionError("The bridge session record is invalid.") from exc


def default_session_store() -> BridgeSessionStore:
    runtime_directory = os.environ.get("AICAD_RUNTIME_DIR")
    if runtime_directory:
        return BridgeSessionStore(runtime_directory)
    return BridgeSessionStore(user_runtime_dir("ai-cad-workbench", appauthor=False))
