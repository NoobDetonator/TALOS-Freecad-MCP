from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from aicad.core.tool_registry import build_default_registry
from aicad.orchestration import (
    AiOrchestrator,
    DEFAULT_DEEPSEEK_MODEL,
    DeepSeekProvider,
    DeepSeekProviderError,
    InvalidProviderResponseError,
    ProviderRequest,
    tool_definition_from_spec,
)


def provider_request(*, with_tools: bool = True) -> ProviderRequest:
    registry = build_default_registry()
    tools = (
        (tool_definition_from_spec(registry.get_spec("cad.create_box")),)
        if with_tools
        else ()
    )
    return ProviderRequest(
        instructions="Plan safe CAD work without executable code.",
        user_message="Crie uma caixa de 10 por 20 por 30 milímetros.",
        context={"document": {"active": False}},
        tools=tools,
        max_tool_calls=1 if tools else 0,
    )


def mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_deepseek_request_uses_current_model_and_translates_tool_names() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_box_1",
                                    "type": "function",
                                    "function": {
                                        "name": "cad__create_box",
                                        "arguments": json.dumps(
                                            {
                                                "length": 10,
                                                "width": 20,
                                                "height": 30,
                                                "name": "DeepSeekBox",
                                            }
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    provider = DeepSeekProvider(
        SecretStr("ds-secret-test"),
        client=mock_client(handler),
    )
    response = provider.create_response(provider_request())

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == "Bearer ds-secret-test"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == DEFAULT_DEEPSEEK_MODEL
    assert body["thinking"] == {"type": "disabled"}
    assert body["stream"] is False
    assert body["tool_choice"] == "auto"
    assert body["tools"][0]["function"]["name"] == "cad__create_box"
    assert "Current CAD context" in body["messages"][1]["content"]
    assert response.tool_calls[0].name == "cad.create_box"
    assert response.tool_calls[0].arguments["height"] == 30


def test_deepseek_plain_text_response_does_not_require_tools() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "tools" not in body
        assert "tool_choice" not in body
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Documento vazio."}}]},
        )

    response = DeepSeekProvider(
        SecretStr("ds-test"),
        client=mock_client(handler),
    ).create_response(provider_request(with_tools=False))

    assert response.message == "Documento vazio."
    assert response.plan == ("Documento vazio.",)
    assert response.tool_calls == ()


@pytest.mark.parametrize(
    "response_json",
    [
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_bad",
                                "type": "function",
                                "function": {
                                    "name": "cad__create_box",
                                    "arguments": "not-json",
                                },
                            }
                        ],
                    }
                }
            ]
        },
        {"choices": [{"message": {"content": None, "tool_calls": []}}]},
        {"choices": []},
    ],
)
def test_deepseek_rejects_malformed_responses(response_json: object) -> None:
    client = mock_client(lambda request: httpx.Response(200, json=response_json))

    with pytest.raises(DeepSeekProviderError):
        DeepSeekProvider(SecretStr("ds-test"), client=client).create_response(
            provider_request()
        )


def test_deepseek_redacts_http_errors_and_secret() -> None:
    secret = "ds-never-show-this"
    client = mock_client(
        lambda request: httpx.Response(
            401,
            json={"error": {"message": secret}},
        )
    )

    with pytest.raises(DeepSeekProviderError) as captured:
        DeepSeekProvider(SecretStr(secret), client=client).create_response(
            provider_request()
        )

    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)


def test_deepseek_tool_arguments_are_revalidated_by_orchestrator() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_incomplete",
                                    "type": "function",
                                    "function": {
                                        "name": "cad__create_box",
                                        "arguments": json.dumps(
                                            {"length": 10, "width": 20}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    provider = DeepSeekProvider(SecretStr("ds-test"), client=mock_client(handler))

    with pytest.raises(InvalidProviderResponseError, match="tool call"):
        AiOrchestrator(build_default_registry(), provider).create_plan(
            "Crie uma caixa."
        )
