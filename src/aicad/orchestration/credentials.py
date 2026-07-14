from __future__ import annotations

import re
from typing import Protocol

import keyring
from keyring.errors import PasswordDeleteError
from pydantic import SecretStr


CREDENTIAL_SERVICE = "ai-cad-workbench"
_PROVIDER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_MAX_API_KEY_CHARS = 8192


class CredentialStoreError(RuntimeError):
    """A credential vault operation failed without exposing secret material."""


class CredentialBackend(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...

    def set_password(
        self,
        service_name: str,
        username: str,
        password: str,
    ) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...


class CredentialStore:
    """Store provider API keys in the operating-system credential vault."""

    def __init__(self, backend: CredentialBackend | None = None) -> None:
        self._backend = backend if backend is not None else keyring

    def has_api_key(self, provider_id: str) -> bool:
        return self.get_api_key(provider_id) is not None

    def get_api_key(self, provider_id: str) -> SecretStr | None:
        account = self._account_name(provider_id)
        try:
            value = self._backend.get_password(CREDENTIAL_SERVICE, account)
        except Exception as exc:
            raise CredentialStoreError(
                "The operating-system credential vault is unavailable."
            ) from exc
        if value is None:
            return None
        return SecretStr(value)

    def set_api_key(self, provider_id: str, api_key: str) -> None:
        account = self._account_name(provider_id)
        checked_key = self._validate_api_key(api_key)
        try:
            self._backend.set_password(
                CREDENTIAL_SERVICE,
                account,
                checked_key,
            )
        except Exception as exc:
            raise CredentialStoreError(
                "The API key could not be saved in the credential vault."
            ) from exc

    def delete_api_key(self, provider_id: str) -> bool:
        account = self._account_name(provider_id)
        try:
            self._backend.delete_password(CREDENTIAL_SERVICE, account)
        except PasswordDeleteError:
            return False
        except Exception as exc:
            raise CredentialStoreError(
                "The API key could not be removed from the credential vault."
            ) from exc
        return True

    @staticmethod
    def _account_name(provider_id: str) -> str:
        if (
            not isinstance(provider_id, str)
            or _PROVIDER_ID_PATTERN.fullmatch(provider_id) is None
        ):
            raise ValueError("The provider ID has an invalid format.")
        return f"provider:{provider_id}:api-key"

    @staticmethod
    def _validate_api_key(api_key: str) -> str:
        if not isinstance(api_key, str):
            raise ValueError("The API key must be text.")
        checked = api_key.strip()
        if not checked:
            raise ValueError("The API key cannot be empty.")
        if len(checked) > _MAX_API_KEY_CHARS:
            raise ValueError("The API key is unexpectedly long.")
        if any(character.isspace() for character in checked):
            raise ValueError("The API key cannot contain whitespace.")
        return checked
