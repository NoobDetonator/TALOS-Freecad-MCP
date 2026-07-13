from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest

from aicad.bridge.protocol import (
    BridgeErrorCode,
    BridgeRequest,
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
from aicad.core.tool_registry import build_default_registry


def build_request(
    tool_name: str = "cad.get_document_summary",
    arguments: dict[str, object] | None = None,
) -> BridgeRequest:
    return BridgeRequest(
        request_id=uuid4(),
        tool_name=tool_name,
        arguments=arguments or {},
        source="mcp",
    )


def validating_handler(payload: Mapping[str, Any]) -> BridgeResponse:
    request = validate_request_payload(payload, build_default_registry())
    return BridgeResponse(
        request_id=request.request_id,
        status=BridgeResponseStatus.COMPLETED,
        result={"tool_name": request.tool_name},
    )


def test_tcp_transport_round_trips_only_over_loopback() -> None:
    with LocalTcpBridgeServer(validating_handler) as server:
        endpoint = server.endpoint
        request = build_request()
        response = TcpBridgeClient(endpoint).request(request)

        assert endpoint.host == "127.0.0.1"
        assert endpoint.port > 0
        assert response.request_id == request.request_id
        assert response.status is BridgeResponseStatus.COMPLETED
        assert response.result == {"tool_name": "cad.get_document_summary"}


def test_endpoint_rejects_external_hosts_and_hides_the_token() -> None:
    token = create_session_token()
    endpoint = BridgeEndpoint("127.0.0.1", 12345, token)

    assert token not in repr(endpoint)
    with pytest.raises(ValueError, match="loopback"):
        BridgeEndpoint("0.0.0.0", 12345, token)


def test_transport_rejects_invalid_credentials_and_limits() -> None:
    with pytest.raises(ValueError, match="session token"):
        LocalTcpBridgeServer(validating_handler, session_token="")
    with pytest.raises(ValueError, match="positive and finite"):
        LocalTcpBridgeServer(validating_handler, timeout=float("nan"))
    with pytest.raises(ValueError, match="integer"):
        LocalTcpBridgeServer(
            validating_handler,
            max_message_bytes=1024.5,
        )


def test_invalid_session_token_is_rejected_before_dispatch() -> None:
    dispatched: list[Mapping[str, Any]] = []

    def handler(payload: Mapping[str, Any]) -> BridgeResponse:
        dispatched.append(payload)
        return validating_handler(payload)

    with LocalTcpBridgeServer(handler) as server:
        endpoint = server.endpoint
        invalid_endpoint = BridgeEndpoint(
            endpoint.host,
            endpoint.port,
            "invalid-session-token-that-is-long-enough",
        )
        response = TcpBridgeClient(invalid_endpoint).request(build_request())

    assert dispatched == []
    assert response.status is BridgeResponseStatus.REJECTED
    assert response.error is not None
    assert response.error.code is BridgeErrorCode.UNAUTHORIZED


def test_protocol_failures_return_categorized_responses() -> None:
    with LocalTcpBridgeServer(validating_handler) as server:
        response = TcpBridgeClient(server.endpoint).request(
            build_request(tool_name="cad.not_registered")
        )

    assert response.status is BridgeResponseStatus.REJECTED
    assert response.error is not None
    assert response.error.code is BridgeErrorCode.UNKNOWN_TOOL


def test_unexpected_handler_errors_do_not_leak_details() -> None:
    def failing_handler(_: Mapping[str, Any]) -> BridgeResponse:
        raise RuntimeError("sensitive implementation detail")

    with LocalTcpBridgeServer(failing_handler) as server:
        response = TcpBridgeClient(server.endpoint).request(build_request())

    assert response.status is BridgeResponseStatus.FAILED
    assert response.error is not None
    assert response.error.code is BridgeErrorCode.EXECUTION_ERROR
    assert "sensitive" not in response.error.message


def test_message_limit_and_clean_shutdown_are_enforced() -> None:
    server = LocalTcpBridgeServer(
        validating_handler,
        max_message_bytes=256,
    )
    with server:
        endpoint = server.endpoint
        oversized = build_request(arguments={"padding": "x" * 1000})
        with pytest.raises(BridgeTransportError):
            TcpBridgeClient(endpoint, max_message_bytes=4096).request(oversized)

    assert server.is_running is False
    with pytest.raises(BridgeTransportError):
        TcpBridgeClient(endpoint, timeout=0.1).request(build_request())
