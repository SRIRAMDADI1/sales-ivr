"""Azure OpenAI LLM client with token usage capture."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from sales_ivr.models.session import LLMUsage
from sales_ivr.runtime import get_config

_PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "your-key-here",
        "changeme",
        "replace-me",
        "https://your-resource-name.openai.azure.com/",
        "https://your-resource.openai.azure.com/",
    }
)

# Newer models (gpt-5.x and other reasoning models) reject max_tokens; older ones
# may reject max_completion_tokens. Azure names the parameter it wants in the 400.
_TOKEN_PARAM_MODERN = "max_completion_tokens"
_TOKEN_PARAM_LEGACY = "max_tokens"

# Cached probe: None = not checked yet
_deployment_ok: bool | None = None
_unavailable_reason: str | None = None


@dataclass
class ChatMessage:
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_openai(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls is not None:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            msg["name"] = self.name
        return msg


@dataclass
class LLMResult:
    content: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: LLMUsage | None = None
    finish_reason: str | None = None


class BaseLLMClient:
    def chat(
        self,
        *,
        agent_name: str,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> LLMResult:
        raise NotImplementedError


def _is_usable(value: str | None) -> bool:
    if value is None:
        return False
    cleaned = value.strip()
    return bool(cleaned) and cleaned not in _PLACEHOLDER_VALUES


def resolve_azure_credentials() -> tuple[str, str] | None:
    """Return (api_key, endpoint) when both are configured; otherwise None."""

    config = get_config().llm
    api_key = (
        config.api_key.get_secret_value()
        if config.api_key is not None
        else os.environ.get(config.api_key_env)
    )
    endpoint = config.endpoint or os.environ.get(config.endpoint_env)
    if not _is_usable(api_key) or not _is_usable(endpoint):
        return None
    assert api_key is not None and endpoint is not None
    return api_key.strip(), endpoint.strip()


def get_llm_unavailable_reason() -> str | None:
    """Human-readable reason Azure LLM cannot be used, or None if ready."""

    if get_config().llm.provider.lower() != "azure":
        return (
            f"llm.provider is '{get_config().llm.provider}' (must be 'azure' for live quotes)."
        )
    if resolve_azure_credentials() is None:
        return (
            "Azure OpenAI API key or endpoint is missing. "
            "Set them in sales-ivr/.env or config.local.yaml."
        )
    # Trigger probe if needed
    azure_llm_enabled()
    return _unavailable_reason


def is_deployment_unavailable_error(exc: BaseException) -> bool:
    """True for missing/invalid Azure deployment (or auth) that should passthrough."""

    text = str(exc).lower()
    name = type(exc).__name__.lower()
    status = getattr(exc, "status_code", None)
    if status in {401, 403, 404}:
        return True
    if "notfound" in name or "authentication" in name or "permission" in name:
        return True

    err_body = getattr(exc, "body", None)
    if isinstance(err_body, dict):
        nested = err_body.get("error") or {}
        if isinstance(nested, dict):
            code = str(nested.get("code", "")).lower()
            if code in {"deploymentnotfound", "model_not_found", "404"}:
                return True

    markers = (
        "deploymentnotfound",
        "deployment not found",
        "does not exist",
        "model_not_found",
        "access denied",
        "invalid subscription key",
        "unauthorized",
    )
    return any(m in text for m in markers)


def token_limit_param_fallback(exc: BaseException) -> str | None:
    """Return the token-limit parameter Azure asked for, or None if that wasn't the problem."""

    text = str(exc)
    if "not supported with this model" not in text and "Unsupported parameter" not in text:
        return None
    for param in (_TOKEN_PARAM_MODERN, _TOKEN_PARAM_LEGACY):
        if f"'{param}' instead" in text:
            return param
    return None


def mark_deployment_unavailable(reason: str) -> None:
    global _deployment_ok, _unavailable_reason
    _deployment_ok = False
    _unavailable_reason = reason


def _probe_deployment() -> bool:
    """Cheap chat call to verify the configured deployment exists."""

    global _deployment_ok, _unavailable_reason
    if _deployment_ok is not None:
        return _deployment_ok

    creds = resolve_azure_credentials()
    if creds is None:
        _deployment_ok = False
        _unavailable_reason = (
            "Azure OpenAI API key or endpoint is missing. "
            "Set them in sales-ivr/.env or config.local.yaml."
        )
        return False

    api_key, endpoint = creds
    config = get_config().llm
    deployment = config.deployment
    try:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=api_key,
            api_version=config.api_version,
            azure_endpoint=endpoint.rstrip("/"),
        )
        probe_kwargs: dict[str, Any] = {
            "model": deployment,
            "messages": [{"role": "user", "content": "ping"}],
            _TOKEN_PARAM_MODERN: 16,
        }
        try:
            client.chat.completions.create(**probe_kwargs)
        except Exception as exc:  # noqa: BLE001 — retry once with the parameter Azure wants
            fallback = token_limit_param_fallback(exc)
            if fallback is None:
                raise
            probe_kwargs.pop(_TOKEN_PARAM_MODERN)
            probe_kwargs[fallback] = 16
            client.chat.completions.create(**probe_kwargs)
        _deployment_ok = True
        _unavailable_reason = None
        return True
    except Exception as exc:  # noqa: BLE001 — probe must never crash the app
        if is_deployment_unavailable_error(exc):
            mark_deployment_unavailable(
                f"Azure OpenAI deployment '{deployment}' is not available "
                f"({type(exc).__name__}: {exc}). "
                "Create a deployment in Azure whose name matches config.yaml → llm.deployment."
            )
            return False
        mark_deployment_unavailable(
            f"Azure OpenAI is unreachable ({type(exc).__name__}: {exc})."
        )
        return False


def azure_llm_enabled() -> bool:
    """True only when provider is azure, credentials exist, and deployment responds."""

    if get_config().llm.provider.lower() != "azure":
        return False
    if resolve_azure_credentials() is None:
        return False
    return _probe_deployment()


class AzureOpenAIClient(BaseLLMClient):
    def __init__(self) -> None:
        from openai import AzureOpenAI

        creds = resolve_azure_credentials()
        if creds is None:
            raise RuntimeError(
                "Azure OpenAI credentials missing. Put them in sales-ivr/.env or "
                "config.local.yaml (see .env.example / config.local.yaml.example)."
            )
        api_key, endpoint = creds
        config = get_config().llm
        self._deployment = config.deployment
        self._deployment_capable = config.deployment_capable or config.deployment
        self._temperature = config.temperature
        self._max_tokens = config.max_tokens
        self._token_param = _TOKEN_PARAM_MODERN
        self._client = AzureOpenAI(
            api_key=api_key,
            api_version=config.api_version,
            azure_endpoint=endpoint.rstrip("/"),
        )

    def _create_completion(self, kwargs: dict[str, Any]) -> Any:
        try:
            return self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 — retry once with the parameter Azure wants
            fallback = token_limit_param_fallback(exc)
            if fallback is None or fallback == self._token_param:
                raise
            kwargs.pop(self._token_param, None)
            self._token_param = fallback
            kwargs[fallback] = self._max_tokens
            return self._client.chat.completions.create(**kwargs)

    def chat(
        self,
        *,
        agent_name: str,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> LLMResult:
        deployment = model or self._deployment
        kwargs: dict[str, Any] = {
            "model": deployment,
            "messages": [m.to_openai() for m in messages],
            "temperature": self._temperature,
            self._token_param: self._max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if response_format:
            kwargs["response_format"] = response_format

        started = time.perf_counter()
        try:
            response = self._create_completion(kwargs)
        except Exception as exc:
            if is_deployment_unavailable_error(exc):
                mark_deployment_unavailable(
                    f"Azure OpenAI deployment '{deployment}' failed during the call "
                    f"({type(exc).__name__}: {exc})."
                )
            raise
        latency_ms = int((time.perf_counter() - started) * 1000)

        choice = response.choices[0]
        message = choice.message
        tool_calls: list[dict[str, Any]] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        usage = LLMUsage(
            agent_name=agent_name,
            model=deployment,
            prompt_tokens=(response.usage.prompt_tokens if response.usage else 0) or 0,
            completion_tokens=(response.usage.completion_tokens if response.usage else 0) or 0,
            total_tokens=(response.usage.total_tokens if response.usage else 0) or 0,
            latency_ms=latency_ms,
            tool_calls=len(tool_calls),
            finish_reason=choice.finish_reason,
        )

        return LLMResult(
            content=message.content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.finish_reason,
        )


_client: BaseLLMClient | None = None


def get_llm_client() -> BaseLLMClient:
    global _client
    if _client is not None:
        return _client
    if not azure_llm_enabled():
        reason = get_llm_unavailable_reason() or "Azure OpenAI is not available."
        raise RuntimeError(reason)
    _client = AzureOpenAIClient()
    return _client


def set_llm_client(client: BaseLLMClient | None) -> None:
    global _client
    _client = client


def reset_llm_client() -> None:
    global _deployment_ok, _unavailable_reason
    set_llm_client(None)
    _deployment_ok = None
    _unavailable_reason = None


def parse_json_content(content: str | None) -> dict[str, Any]:
    if not content:
        return {}
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)
