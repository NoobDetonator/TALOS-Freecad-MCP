from __future__ import annotations

from keyring.errors import PasswordDeleteError
import pytest

from aicad.orchestration import (
    CREDENTIAL_SERVICE,
    CredentialStore,
    CredentialStoreError,
)


class MemoryCredentialBackend:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.values.get((service_name, username))

    def set_password(
        self,
        service_name: str,
        username: str,
        password: str,
    ) -> None:
        self.values[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        try:
            del self.values[(service_name, username)]
        except KeyError as exc:
            raise PasswordDeleteError("credential not found") from exc


def test_api_key_round_trip_uses_provider_scoped_vault_account() -> None:
    backend = MemoryCredentialBackend()
    store = CredentialStore(backend)

    store.set_api_key("openai", "  sk-test-value  ")
    secret = store.get_api_key("openai")

    assert backend.values == {
        (CREDENTIAL_SERVICE, "provider:openai:api-key"): "sk-test-value"
    }
    assert secret is not None
    assert secret.get_secret_value() == "sk-test-value"
    assert "sk-test-value" not in repr(secret)
    assert store.has_api_key("openai") is True


def test_delete_api_key_is_explicit_and_idempotent() -> None:
    backend = MemoryCredentialBackend()
    store = CredentialStore(backend)
    store.set_api_key("openai", "sk-test-value")

    assert store.delete_api_key("openai") is True
    assert store.delete_api_key("openai") is False
    assert store.has_api_key("openai") is False


@pytest.mark.parametrize(
    ("provider_id", "api_key"),
    [
        ("OpenAI", "sk-test-value"),
        ("../openai", "sk-test-value"),
        ("openai", ""),
        ("openai", "   "),
        ("openai", "key with whitespace"),
    ],
)
def test_invalid_provider_or_key_never_reaches_vault(
    provider_id: str,
    api_key: str,
) -> None:
    backend = MemoryCredentialBackend()

    with pytest.raises(ValueError):
        CredentialStore(backend).set_api_key(provider_id, api_key)

    assert backend.values == {}


def test_vault_errors_are_redacted() -> None:
    class FailingBackend(MemoryCredentialBackend):
        def get_password(self, service_name: str, username: str) -> str | None:
            raise RuntimeError("raw-vault-secret")

    with pytest.raises(CredentialStoreError) as captured:
        CredentialStore(FailingBackend()).get_api_key("openai")

    assert "raw-vault-secret" not in str(captured.value)
