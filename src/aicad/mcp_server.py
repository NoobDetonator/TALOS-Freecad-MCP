from __future__ import annotations

from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from aicad.core.tool_registry import ToolRisk
from aicad.runtime import get_tool_registry


mcp = FastMCP("AI CAD Workbench")
tool_registry = get_tool_registry()


@mcp.tool()
def health() -> dict[str, str]:
    """Check whether the AI CAD MCP process is available."""
    return {"status": "ok", "phase": "local-safe-chat"}


@mcp.tool()
def available_cad_tools() -> list[dict[str, object]]:
    """List the deterministic CAD tools from the shared runtime registry."""
    return [asdict(spec) for spec in tool_registry.list_specs()]


@mcp.tool()
def execute_cad_read_tool(name: str, arguments: dict[str, object]) -> object:
    """Execute a read-only CAD tool; modifications remain blocked over MCP."""
    spec = tool_registry.get_spec(name)
    if spec.risk is not ToolRisk.READ:
        raise PermissionError(
            "CAD modifications over MCP are disabled until the local GUI bridge "
            "can request explicit user confirmation."
        )
    return tool_registry.execute(name, arguments)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
