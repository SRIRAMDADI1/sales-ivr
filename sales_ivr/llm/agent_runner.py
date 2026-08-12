"""Generic LLM agent loop with tools + structured final JSON."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from sales_ivr.llm.client import (
    ChatMessage,
    get_llm_client,
    parse_json_content,
)
from sales_ivr.llm.tools import run_tool, tool_specs
from sales_ivr.models.session import IVRState, LLMUsage
from sales_ivr.runtime import get_config

T = TypeVar("T", bound=BaseModel)


def run_structured_agent(
    *,
    agent_name: str,
    system_prompt: str,
    user_payload: dict[str, Any],
    output_model: type[T],
    state: IVRState,
    enable_tools: bool = True,
    use_capable_model: bool = False,
) -> T:
    """Run an LLM agent until it returns JSON matching output_model.

    Records all LLMUsage onto state.llm_usage for observability.
    """

    client = get_llm_client()
    config = get_config()
    model = None
    if use_capable_model and config.llm.deployment_capable:
        model = config.llm.deployment_capable

    schema = output_model.model_json_schema()
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(
            role="user",
            content=(
                "Session context (JSON):\n"
                f"{json.dumps(user_payload, default=str)}\n\n"
                "Use tools if needed. When finished, respond with ONLY a JSON object "
                f"matching this schema:\n{json.dumps(schema)}"
            ),
        ),
    ]

    tools = tool_specs() if enable_tools else None
    max_rounds = config.runtime.max_agent_tool_rounds
    aggregated_usage = LLMUsage(agent_name=agent_name, model=model or config.llm.deployment)

    for _ in range(max_rounds + 1):
        result = client.chat(
            agent_name=agent_name,
            messages=messages,
            tools=tools,
            model=model,
        )
        if result.usage:
            aggregated_usage.prompt_tokens += result.usage.prompt_tokens
            aggregated_usage.completion_tokens += result.usage.completion_tokens
            aggregated_usage.total_tokens += result.usage.total_tokens
            aggregated_usage.latency_ms += result.usage.latency_ms
            aggregated_usage.tool_calls += result.usage.tool_calls
            aggregated_usage.model = result.usage.model
            aggregated_usage.finish_reason = result.usage.finish_reason

        if result.tool_calls:
            messages.append(
                ChatMessage(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls,
                )
            )
            for tc in result.tool_calls:
                fn = tc["function"]
                tool_result = run_tool(fn["name"], fn.get("arguments", "{}"))
                messages.append(
                    ChatMessage(
                        role="tool",
                        tool_call_id=tc["id"],
                        name=fn["name"],
                        content=tool_result,
                    )
                )
            continue

        # Final answer
        try:
            data = parse_json_content(result.content)
            parsed = output_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            # One repair attempt
            messages.append(ChatMessage(role="assistant", content=result.content or ""))
            messages.append(
                ChatMessage(
                    role="user",
                    content=(
                        f"Your previous response was invalid ({exc}). "
                        "Return ONLY valid JSON matching the schema."
                    ),
                )
            )
            repair = client.chat(agent_name=agent_name, messages=messages, model=model)
            if repair.usage:
                aggregated_usage.prompt_tokens += repair.usage.prompt_tokens
                aggregated_usage.completion_tokens += repair.usage.completion_tokens
                aggregated_usage.total_tokens += repair.usage.total_tokens
                aggregated_usage.latency_ms += repair.usage.latency_ms
            data = parse_json_content(repair.content)
            parsed = output_model.model_validate(data)

        state.record_usage(aggregated_usage)
        return parsed

    state.record_usage(aggregated_usage)
    raise RuntimeError(f"Agent {agent_name} exceeded tool rounds without final answer")
