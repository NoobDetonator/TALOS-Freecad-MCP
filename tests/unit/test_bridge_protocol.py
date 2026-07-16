from uuid import UUID

import pytest
from pydantic import ValidationError

from aicad.bridge.protocol import (
    PROTOCOL_VERSION,
    BridgeError,
    BridgeErrorCode,
    BridgeProtocolError,
    BridgeRequest,
    BridgeResponse,
    BridgeResponseStatus,
    validate_request_payload,
)
from aicad.core.tool_registry import build_default_registry
from aicad.core.tool_results import ToolErrorCategory, ToolRecoveryActionType


REQUEST_ID = "12345678-1234-5678-9234-567812345678"


def request_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": REQUEST_ID,
        "tool_name": "cad.get_document_summary",
        "arguments": {},
        "source": "mcp",
    }
    payload.update(changes)
    return payload


def test_valid_request_round_trips_as_json() -> None:
    request = validate_request_payload(request_payload(), build_default_registry())
    encoded = request.model_dump_json()
    decoded = BridgeRequest.model_validate_json(encoded)

    assert decoded.model_dump(mode="json") == request_payload()
    assert decoded.request_id == UUID(REQUEST_ID)


def test_request_rejects_unsupported_protocol_versions() -> None:
    with pytest.raises(BridgeProtocolError) as captured:
        validate_request_payload(
            request_payload(protocol_version="2.0"),
            build_default_registry(),
        )

    assert captured.value.code is BridgeErrorCode.UNSUPPORTED_VERSION
    assert captured.value.error.details["expected"] == PROTOCOL_VERSION


def test_request_rejects_unknown_or_code_like_tool_names() -> None:
    with pytest.raises(BridgeProtocolError) as unknown:
        validate_request_payload(
            request_payload(tool_name="cad.not_registered"),
            build_default_registry(),
        )
    assert unknown.value.code is BridgeErrorCode.UNKNOWN_TOOL

    with pytest.raises(BridgeProtocolError) as code_like:
        validate_request_payload(
            request_payload(tool_name="python.eval"),
            build_default_registry(),
        )
    assert code_like.value.code is BridgeErrorCode.INVALID_REQUEST


def test_request_uses_registry_argument_validation() -> None:
    with pytest.raises(BridgeProtocolError) as captured:
        validate_request_payload(
            request_payload(
                tool_name="cad.create_box",
                arguments={
                    "length": 10,
                    "width": 20,
                    "height": 30,
                    "python": "print('unsafe')",
                },
            ),
            build_default_registry(),
        )

    assert captured.value.code is BridgeErrorCode.INVALID_ARGUMENTS


def test_request_rejects_extra_envelope_fields() -> None:
    with pytest.raises(BridgeProtocolError) as captured:
        validate_request_payload(
            request_payload(unexpected=True),
            build_default_registry(),
        )

    assert captured.value.code is BridgeErrorCode.INVALID_REQUEST
    assert captured.value.error.details["issues"][0]["location"] == "unexpected"


def test_response_enforces_status_payload_invariants() -> None:
    completed = BridgeResponse(
        request_id=REQUEST_ID,
        status=BridgeResponseStatus.COMPLETED,
        result={"active": False},
    )
    assert completed.model_dump(mode="json")["result"] == {"active": False}

    pending = BridgeResponse(
        request_id=REQUEST_ID,
        status=BridgeResponseStatus.PENDING_CONFIRMATION,
    )
    assert pending.error is None

    with pytest.raises(ValidationError):
        BridgeResponse(
            request_id=REQUEST_ID,
            status=BridgeResponseStatus.FAILED,
        )

    failed = BridgeResponse(
        request_id=REQUEST_ID,
        status=BridgeResponseStatus.FAILED,
        error=BridgeError(
            code=BridgeErrorCode.EXECUTION_ERROR,
            message="The CAD operation failed.",
        ),
    )
    assert failed.result is None
    assert failed.error.category is ToolErrorCategory.INTERNAL
    assert failed.error.safe_state_restored is None


def test_bridge_errors_add_deterministic_recovery_profiles() -> None:
    unknown = BridgeError(
        code=BridgeErrorCode.UNKNOWN_TOOL,
        message="The requested CAD tool is not registered.",
    )
    assert unknown.category is ToolErrorCategory.UNAVAILABLE_CAPABILITY
    assert unknown.retryable is False
    assert unknown.safe_state_restored is True
    assert (
        unknown.suggested_actions[0].action
        is ToolRecoveryActionType.SEARCH_CAPABILITIES
    )

    disconnected = BridgeError(
        code=BridgeErrorCode.TRANSPORT_UNAVAILABLE,
        message="The bridge disconnected.",
    )
    assert disconnected.category is ToolErrorCategory.TRANSPORT
    assert disconnected.retryable is True
    assert disconnected.safe_state_restored is None
