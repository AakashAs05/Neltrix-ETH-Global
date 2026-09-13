"""Typed entry point for The Graph's Subgraph MCP server.

Separate from the core pipeline, which queries the gateway directly. MCP is
for the natural-language surface, called by an MCP-aware agent.
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
