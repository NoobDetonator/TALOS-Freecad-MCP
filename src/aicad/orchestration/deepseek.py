from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

import httpx
from pydantic import SecretStr

from aicad.orchestration.models import (
    ProviderAssistantMessage,
    ProviderRequest,
    ProviderResponse,
    ProviderToolResultMessage,
    ProviderToolCall,
)
from aicad.orchestration.provider import AiProviderError


DEEPSEEK_CHAT_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
SUPPORTED_DEEPSEEK_MODELS = frozenset(
    {"deepseek-v4-flash", "deepseek-v4-pro"}
)


class DeepSeekProviderError(AiProviderError):
    """A redacted DeepSeek transport or response error."""


class DeepSeekProvider:
    """Provider adapter for DeepSeek's OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        api_key: SecretStr,
        *,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not isinstance(api_key, SecretStr) or not api_key.get_secret_value().strip():
            raise ValueError("A DeepSeek API key is required.")
        if model not in SUPPORTED_DEEPSEEK_MODELS:
            raise ValueError("Unsupported DeepSeek model.")
        if timeout_seconds <= 0:
            raise ValueError("The DeepSeek timeout must be positive.")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._client = client or httpx.Client(timeout=self._timeout)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> DeepSeekProvider:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def create_response(self, request: ProviderRequest) -> ProviderResponse:
        aliases = {
            self._tool_alias(tool.name): tool.name for tool in request.tools
        }
        body = self._request_body(request, aliases)
        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        try:
            response = self._client.post(
                DEEPSEEK_CHAT_URL,
                headers=headers,
                json=body,
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            return self._parse_response(payload, aliases)
        except DeepSeekProviderError:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError):
            raise DeepSeekProviderError(
                "DeepSeek is unavailable or returned an invalid response."
            ) from None

    def _request_body(
        self,
        request: ProviderRequest,
        aliases: Mapping[str, str],
    ) -> dict[str, Any]:
        context_json = json.dumps(
            request.context,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        system_message = (
            request.instructions
            + " Respond in concise Brazilian Portuguese. When a supplied function "
            "is needed, call it instead of inventing a textual result. Propose no "
            f"more than {request.max_tool_calls} function call(s)."
        )
        user_message = request.user_message
        if request.context:
            user_message += "\n\nCurrent CAD context (JSON):\n" + context_json
        tools = []
        canonical_by_alias = dict(aliases)
        for tool in request.tools:
            alias = self._tool_alias(tool.name)
            if canonical_by_alias.get(alias) != tool.name:
                raise DeepSeekProviderError("A tool name cannot be exposed safely.")
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": alias,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
            )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]
        for item in request.history:
            if isinstance(item, ProviderAssistantMessage):
                messages.append(
                    {
                        "role": "assistant",
                        "content": item.content or None,
                        "tool_calls": [
                            {
                                "id": call.call_id,
                                "type": "function",
                                "function": {
                                    "name": self._history_tool_alias(
                                        call.name,
                                        aliases,
                                    ),
                                    "arguments": json.dumps(
                                        call.arguments,
                                        ensure_ascii=False,
                                        allow_nan=False,
                                        separators=(",", ":"),
                                    ),
                                },
                            }
                            for call in item.tool_calls
                        ],
                    }
                )
            elif isinstance(item, ProviderToolResultMessage):
                self._history_tool_alias(item.name, aliases)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": item.call_id,
                        "content": json.dumps(
                            {
                                "status": item.status,
                                "summary": item.summary,
                                "result": item.result,
                                "error_code": item.error_code,
                            },
                            ensure_ascii=False,
                            allow_nan=False,
                            separators=(",", ":"),
                        ),
                    }
                )
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "thinking": {"type": "disabled"},
            "stream": False,
            "max_tokens": 1200,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        return body

    @classmethod
    def _history_tool_alias(
        cls,
        canonical_name: str,
        aliases: Mapping[str, str],
    ) -> str:
        alias = cls._tool_alias(canonical_name)
        if aliases.get(alias) != canonical_name:
            raise DeepSeekProviderError(
                "Provider history references a tool that is not allowed."
            )
        return alias

    @staticmethod
    def _tool_alias(canonical_name: str) -> str:
        alias = canonical_name.replace(".", "__")
        if len(alias) > 64 or not all(
            character.isascii()
            and (character.isalnum() or character in {"_", "-"})
            for character in alias
        ):
            raise DeepSeekProviderError("A tool name cannot be exposed safely.")
        return alias

    @classmethod
    def _parse_response(
        cls,
        payload: Any,
        aliases: Mapping[str, str],
    ) -> ProviderResponse:
        if not isinstance(payload, Mapping):
            raise DeepSeekProviderError("DeepSeek returned an invalid response.")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise DeepSeekProviderError("DeepSeek returned an invalid response.")
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise DeepSeekProviderError("DeepSeek returned an invalid response.")
        message = choice.get("message")
        if not isinstance(message, Mapping):
            raise DeepSeekProviderError("DeepSeek returned an invalid response.")

        content_value = message.get("content")
        content = content_value.strip() if isinstance(content_value, str) else ""
        raw_tool_calls = message.get("tool_calls", [])
        if raw_tool_calls is None:
            raw_tool_calls = []
        if not isinstance(raw_tool_calls, list):
            raise DeepSeekProviderError("DeepSeek returned invalid tool calls.")
        tool_calls = tuple(
            cls._parse_tool_call(item, aliases) for item in raw_tool_calls
        )
        if not content and not tool_calls:
            raise DeepSeekProviderError("DeepSeek returned an empty response.")

        if content:
            intention = cls._bounded(content, 500)
            plan = (cls._bounded(content, 500),)
            display_message = content[:4000]
        else:
            intention = "Atender ao pedido com uma ferramenta CAD permitida."
            plan = tuple(
                f"Revisar a chamada proposta para {call.name}."
                for call in tool_calls
            )
            display_message = "A DeepSeek preparou uma operação CAD para revisão."
        return ProviderResponse(
            intention=intention,
            assumptions=(),
            plan=plan,
            message=display_message,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _parse_tool_call(
        raw_call: Any,
        aliases: Mapping[str, str],
    ) -> ProviderToolCall:
        if not isinstance(raw_call, Mapping) or raw_call.get("type") != "function":
            raise DeepSeekProviderError("DeepSeek returned an invalid tool call.")
        function = raw_call.get("function")
        if not isinstance(function, Mapping):
            raise DeepSeekProviderError("DeepSeek returned an invalid tool call.")
        alias = function.get("name")
        call_id = raw_call.get("id")
        raw_arguments = function.get("arguments")
        if not isinstance(alias, str) or alias not in aliases:
            raise DeepSeekProviderError("DeepSeek returned an unknown tool call.")
        if not isinstance(call_id, str) or not call_id:
            raise DeepSeekProviderError("DeepSeek returned an invalid tool call.")
        if not isinstance(raw_arguments, str):
            raise DeepSeekProviderError("DeepSeek returned invalid tool arguments.")
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            raise DeepSeekProviderError(
                "DeepSeek returned invalid tool arguments."
            ) from None
        if not isinstance(arguments, dict):
            raise DeepSeekProviderError("DeepSeek returned invalid tool arguments.")
        return ProviderToolCall(
            call_id=call_id,
            name=aliases[alias],
            arguments=arguments,
        )

    @staticmethod
    def _bounded(value: str, maximum: int) -> str:
        cleaned = " ".join(value.split())
        return cleaned[:maximum] or "Resposta da DeepSeek."
