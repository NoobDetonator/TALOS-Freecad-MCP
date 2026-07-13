"""Transport-independent contracts for the local MCP-to-GUI bridge."""

from aicad.bridge.protocol import (
    PROTOCOL_VERSION,
    BridgeError,
    BridgeErrorCode,
    BridgeProtocolError,
    BridgeRequest,
    BridgeRequestSource,
    BridgeResponse,
    BridgeResponseStatus,
    validate_request_payload,
)
from aicad.bridge.transport import (
    BridgeEndpoint,
    BridgeTransportError,
    LocalTcpBridgeServer,
    TcpBridgeClient,
    create_session_token,
)
from aicad.bridge.dispatcher import BridgeDispatcher
from aicad.bridge.session import (
    BridgeSessionError,
    BridgeSessionRecord,
    BridgeSessionStore,
    default_session_store,
)

__all__ = [
    "PROTOCOL_VERSION",
    "BridgeError",
    "BridgeErrorCode",
    "BridgeProtocolError",
    "BridgeRequest",
    "BridgeRequestSource",
    "BridgeResponse",
    "BridgeResponseStatus",
    "validate_request_payload",
    "BridgeEndpoint",
    "BridgeTransportError",
    "LocalTcpBridgeServer",
    "TcpBridgeClient",
    "create_session_token",
    "BridgeDispatcher",
    "BridgeSessionError",
    "BridgeSessionRecord",
    "BridgeSessionStore",
    "default_session_store",
]
