from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from aicad.orchestration.models import ProviderRequest, ProviderResponse


ProviderResult = ProviderResponse | Mapping[str, Any]


class AiProviderError(RuntimeError):
    """Base error raised by provider adapters without exposing credentials."""


@runtime_checkable
class AiProvider(Protocol):
    """Minimal synchronous boundary implemented by concrete AI providers."""

    def create_response(self, request: ProviderRequest) -> ProviderResult:
        """Return one structured planning response."""
