from pathlib import Path
from uuid import uuid4

import pytest

from aicad.bridge.session import (
    BridgeSessionError,
    BridgeSessionStore,
    default_session_store,
)
from aicad.bridge.transport import BridgeEndpoint, create_session_token


def endpoint() -> BridgeEndpoint:
    return BridgeEndpoint("127.0.0.1", 43210, create_session_token())


def test_session_record_is_published_atomically_and_loaded(tmp_path: Path) -> None:
    store = BridgeSessionStore(tmp_path / ".runtime")
    bridge_endpoint = endpoint()

    published = store.publish(bridge_endpoint, process_id=1234)
    loaded = store.load()

    assert loaded == published
    assert loaded.endpoint == bridge_endpoint
    assert loaded.process_id == 1234
    assert bridge_endpoint.session_token not in repr(loaded)
    assert store.path.is_file()
    assert list(store.path.parent.glob("*.tmp")) == []


def test_session_store_rejects_invalid_records_without_leaking_input(
    tmp_path: Path,
) -> None:
    store = BridgeSessionStore(tmp_path / ".runtime")
    store.path.parent.mkdir(parents=True)
    store.path.write_text(
        '{"session_token":"super-secret-invalid-token"}',
        encoding="utf-8",
    )

    with pytest.raises(BridgeSessionError) as captured:
        store.load()

    assert "super-secret" not in str(captured.value)


def test_clear_removes_only_the_matching_session(tmp_path: Path) -> None:
    store = BridgeSessionStore(tmp_path / ".runtime")
    first = store.publish(endpoint())

    assert store.clear(uuid4()) is False
    assert store.load().session_id == first.session_id

    second = store.publish(endpoint())
    assert store.clear(first.session_id) is False
    assert store.load().session_id == second.session_id
    assert store.clear(second.session_id) is True
    assert store.path.exists() is False


def test_publish_rejects_invalid_process_ids(tmp_path: Path) -> None:
    store = BridgeSessionStore(tmp_path / ".runtime")

    with pytest.raises(ValueError):
        store.publish(endpoint(), process_id=0)


def test_default_store_uses_explicit_runtime_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("AICAD_RUNTIME_DIR", str(runtime))
    monkeypatch.delenv("AICAD_PROJECT_ROOT", raising=False)

    assert default_session_store().path == runtime / "bridge-session.json"


def test_default_store_uses_the_user_runtime_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AICAD_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(
        "aicad.bridge.session.user_runtime_dir",
        lambda *_args, **_kwargs: str(tmp_path / "user-runtime"),
    )

    assert (
        default_session_store().path
        == tmp_path / "user-runtime" / "bridge-session.json"
    )


def test_default_store_does_not_put_session_token_in_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    user_runtime = tmp_path / "user-runtime"
    monkeypatch.delenv("AICAD_RUNTIME_DIR", raising=False)
    monkeypatch.setenv("AICAD_PROJECT_ROOT", str(project_root))
    monkeypatch.setattr(
        "aicad.bridge.session.user_runtime_dir",
        lambda *_args, **_kwargs: str(user_runtime),
    )
    assert default_session_store().path.parent == user_runtime
