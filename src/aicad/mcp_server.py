from __future__ import annotations

from dataclasses import asdict
from uuid import UUID, uuid4

from mcp.server.fastmcp import FastMCP

from aicad.bridge.protocol import BridgeRequest, BridgeResponse, BridgeResponseStatus
from aicad.bridge.session import BridgeSessionError, default_session_store
from aicad.bridge.transport import BridgeTransportError, TcpBridgeClient
from aicad.core.tool_registry import ToolRisk
from aicad.runtime import get_tool_registry


mcp = FastMCP("AI CAD Workbench")
tool_registry = get_tool_registry()


@mcp.tool()
def health() -> dict[str, str]:
    """Check whether the AI CAD MCP process is available."""
    return {"status": "ok", "phase": "mcp-gui-bridge"}


@mcp.tool()
def available_cad_tools() -> list[dict[str, object]]:
    """List the deterministic CAD tools from the shared runtime registry."""
    return [asdict(spec) for spec in tool_registry.list_specs()]


def _build_bridge_request(
    name: str,
    arguments: dict[str, object],
    request_id: str | None = None,
) -> BridgeRequest:
    checked_arguments = tool_registry.validate_arguments(name, arguments)
    identifier = UUID(request_id) if request_id is not None else uuid4()
    return BridgeRequest(
        request_id=identifier,
        tool_name=name,
        arguments=checked_arguments,
        source="mcp",
    )


def _send_bridge_request(request: BridgeRequest) -> BridgeResponse:
    try:
        session = default_session_store().load()
        return TcpBridgeClient(session.endpoint).request(request)
    except (BridgeSessionError, BridgeTransportError) as exc:
        raise RuntimeError(
            "The FreeCAD GUI bridge is unavailable or did not respond."
        ) from exc


@mcp.tool()
def request_cad_tool(
    name: str,
    arguments: dict[str, object],
    request_id: str | None = None,
) -> dict[str, object]:
    """Request any registered CAD tool through the authenticated GUI bridge."""

    request = _build_bridge_request(name, arguments, request_id)
    return _send_bridge_request(request).model_dump(mode="json")


@mcp.tool()
def execute_cad_read_tool(name: str, arguments: dict[str, object]) -> object:
    """Execute a read-only CAD tool through the active FreeCAD GUI bridge."""
    spec = tool_registry.get_spec(name)
    if spec.risk is not ToolRisk.READ:
        raise PermissionError(
            "Use request_cad_tool for modifications that require GUI confirmation."
        )
    request = _build_bridge_request(name, arguments)
    response = _send_bridge_request(request)
    if response.status is BridgeResponseStatus.COMPLETED:
        return response.result
    message = (
        response.error.message
        if response.error is not None
        else "The CAD read did not complete."
    )
    raise RuntimeError(message)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
