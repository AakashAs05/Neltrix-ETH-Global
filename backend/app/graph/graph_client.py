"""Thin, generic GraphQL client for The Graph's decentralized-network gateway.

Every Graph query in this project — regardless of which protocol or chain it
targets — goes through this one client. It knows nothing about DEXes,
pools, or OHLCV; it just authenticates, POSTs a query to a subgraph ID, and
surfaces GraphQL errors as Python exceptions instead of silently returning
partial data.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_KEY = os.getenv("GRAPH_API_KEY", "")
GRAPH_GATEWAY_URL = os.getenv("GRAPH_GATEWAY_URL", "https://gateway.thegraph.com/api")


class GraphQueryError(RuntimeError):
    """Raised when the gateway responds with GraphQL-level errors."""


class GraphClient:
    """Executes GraphQL queries against a subgraph on The Graph's gateway."""

    def __init__(self, api_key: str | None = None, gateway_url: str | None = None, timeout: float = 15.0):
        self.api_key = api_key or GRAPH_API_KEY
        self.gateway_url = (gateway_url or GRAPH_GATEWAY_URL).rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError(
                "GRAPH_API_KEY is not set. Copy .env.example to .env and add your "
                "Graph API key from https://thegraph.com/studio/apikeys/"
            )

    def _endpoint(self, subgraph_id: str) -> str:
        return f"{self.gateway_url}/{self.api_key}/subgraphs/id/{subgraph_id}"

    def query(
        self,
        subgraph_id: str,
        query: str,
        variables: dict[str, Any] | None = None,
        retries: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> dict[str, Any]:
        """Run one GraphQL query against `subgraph_id` and return `data`.

        Raises GraphQueryError on GraphQL errors so callers don't have to
        remember to check for an "errors" key on every response.

        The Graph's gateway load-balances each query across several
        indexers on the decentralized network; an individual indexer being
        slow, unsynced, or briefly unhealthy shows up as a "bad indexers"
        GraphQL error rather than an HTTP failure, even though a retry a
        moment later routes around it and succeeds. So a handful of
        retries here is standard practice for this API, not a sign of a
        broken query.
        """
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        last_error: GraphQueryError | None = None
        for attempt in range(retries):
            response = httpx.post(self._endpoint(subgraph_id), json=payload, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()

            if "errors" not in body:
                return body["data"]

            last_error = GraphQueryError(str(body["errors"]))
            if attempt < retries - 1:
                time.sleep(retry_backoff_seconds * (attempt + 1))

        raise last_error  # type: ignore[misc]


_default_client: GraphClient | None = None


def get_client() -> GraphClient:
    """Lazily-constructed module-level client, shared across requests."""
    global _default_client
    if _default_client is None:
        _default_client = GraphClient()
    return _default_client
