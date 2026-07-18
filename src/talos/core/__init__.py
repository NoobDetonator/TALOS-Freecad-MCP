"""Provider- and CAD-independent domain logic."""

from talos.core.capabilities import CapabilityCatalog
from talos.core.context import (
    ContextDetailLevel,
    ContextSnapshot,
    ContextStateTracker,
    DocumentStateToken,
)
from talos.core.tool_selector import (
    ToolMatch,
    ToolSelection,
    ToolSelector,
    normalize_search_text,
)
from talos.core.tool_results import (
    AffectedObjects,
    ToolError,
    ToolErrorCategory,
    ToolErrorCode,
    ToolRecoveryAction,
    ToolRecoveryActionType,
    ToolResultEnvelope,
    ToolResultStatus,
    ToolValidation,
)


__all__ = [
    "AffectedObjects",
    "CapabilityCatalog",
    "ContextDetailLevel",
    "ContextSnapshot",
    "ContextStateTracker",
    "DocumentStateToken",
    "ToolMatch",
    "ToolSelection",
    "ToolSelector",
    "ToolError",
    "ToolErrorCategory",
    "ToolErrorCode",
    "ToolRecoveryAction",
    "ToolRecoveryActionType",
    "ToolResultEnvelope",
    "ToolResultStatus",
    "ToolValidation",
    "normalize_search_text",
]
