"""Transport-independent contracts for the local MCP-to-GUI bridge."""

from talos.bridge.protocol import (
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
from talos.bridge.transport import (
    BridgeEndpoint,
    BridgeTransportError,
    LocalTcpBridgeServer,
    TcpBridgeClient,
    create_session_token,
)
from talos.bridge.dispatcher import BridgeDispatcher
from talos.bridge.session import (
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
