"""Wraps calls to The Graph's Subgraph MCP server for natural-language queries.

This is deliberately separate from graph_client.py / standardized_query.py,
which power the core `/api/ohlcv` and `/api/analyse` pipeline directly
against the gateway (fast, deterministic, easy to test). Subgraph MCP is
used specifically for the natural-language surface described in the plan,
e.g. an agent asking "show me bearish patterns forming on ETH/USDC pools
across DEXs", where translating free text into a GraphQL query is the
actual value MCP adds.

Not wired into the core pipeline: MCP tool calls in this codebase are made
by an MCP-aware agent/client (see agent/), not by this FastAPI service
calling itself. This module documents the shape that integration takes and
gives the agent a typed entry point.
"""

from __future__ import annotations

from dataclasses import dataclass

SUBGRAPH_MCP_ENDPOINT = "https://subgraphs.mcp.thegraph.com/mcp"


@dataclass(frozen=True)
class NaturalLanguageQuery:
    prompt: str
    protocol_hint: str | None = None


def build_mcp_request(nl_query: NaturalLanguageQuery) -> dict:
    """Shape of the request an MCP client sends to Subgraph MCP's
    `search-subgraphs` / `execute-query` tools for a natural-language ask.

    Returns a plain dict (not a live call) so this stays testable without
    a network round-trip; agent/pay_and_analyse.ts (or an MCP-aware agent
    runtime) is what actually dispatches it to SUBGRAPH_MCP_ENDPOINT.
    """
    return {
        "tool": "execute-query",
        "arguments": {
            "prompt": nl_query.prompt,
            "protocol_hint": nl_query.protocol_hint,
        },
    }
