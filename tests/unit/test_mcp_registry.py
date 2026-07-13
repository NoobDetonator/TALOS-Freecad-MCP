import pytest

from aicad.mcp_server import (
    available_cad_tools,
    execute_cad_read_tool,
    tool_registry,
)
from aicad.runtime import get_tool_registry


def test_mcp_uses_the_shared_runtime_registry() -> None:
    assert tool_registry is get_tool_registry()
    assert [tool["name"] for tool in available_cad_tools()] == [
        spec.name for spec in tool_registry.list_specs()
    ]


def test_mcp_blocks_modifications_until_confirmation_bridge_exists() -> None:
    with pytest.raises(PermissionError, match="modifications over MCP are disabled"):
        execute_cad_read_tool("cad.undo", {})
