"""Read-only MCP server for the local Pulse usage ledger.

Cursor launches this over stdio (`python -m sales_ivr.mcp.pulse`). Each tool reads
the same JSONL file the web app writes. Nothing here records or changes usage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from sales_ivr.web.pulse_ledger import agent_usage, recent_calls, summary

# Same file config.py loads, so PULSE_LEDGER_PATH in .env applies here too.
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=False)

_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

server = MCPServer(
    "Pulse",
    instructions=(
        "Read-only view of Firstpass Quotes Pulse: local AI call cost, tokens, "
        "latency, and per-agent usage. These tools never record or change usage. "
        "They see the ledger on this machine, which is the same file the local "
        "web app writes."
    ),
)


@server.tool(annotations=_READ_ONLY)
def pulse_summary() -> dict[str, Any]:
    """Roll up every AI call on this machine: cost, tokens, latency, agents, and models."""

    return summary()


@server.tool(annotations=_READ_ONLY)
def pulse_recent(
    limit: Annotated[
        int,
        Field(ge=1, le=50, description="How many newest calls to return."),
    ] = 12,
) -> dict[str, Any]:
    """Return the newest AI calls, most recent first."""

    calls = recent_calls(limit)
    return {"count": len(calls), "calls": calls}


@server.tool(annotations=_READ_ONLY)
def pulse_agent(
    agent_name: Annotated[str, Field(description="Agent name, matched case-insensitively.")],
    recent_limit: Annotated[
        int,
        Field(ge=1, le=50, description="How many of that agent's newest calls to include."),
    ] = 12,
) -> dict[str, Any]:
    """Roll up one agent's calls, tokens, cost, and latency.

    When the name does not match, the result lists known agents and close suggestions.
    """

    return agent_usage(agent_name, recent_limit)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
