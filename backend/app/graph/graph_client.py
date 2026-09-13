"""Generic GraphQL client for The Graph's gateway.

Knows nothing about DEXes or pools. It authenticates, POSTs a query, and
raises on GraphQL errors instead of returning half a response.
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

    # Paged swap queries against a busy pool are genuinely slow; 15s was
    # tight enough that healthy-but-loaded indexers timed out.
    def __init__(self, api_key: str | None = None, gateway_url: str | None = None, timeout: float = 30.0):
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
        """Run a query and return `data`, retrying transient indexer failures.

        The gateway load-balances across indexers, so an unhealthy one shows
        up as a "bad indexers" error or a timeout that a retry routes around.
        Both are re-raised as GraphQueryError if every attempt fails.
        """
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        last_error: GraphQueryError | None = None
        for attempt in range(retries):
            try:
                response = httpx.post(self._endpoint(subgraph_id), json=payload, timeout=self.timeout)
                response.raise_for_status()
                body = response.json()

                if "errors" not in body:
                    return body["data"]

                last_error = GraphQueryError(str(body["errors"]))
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = GraphQueryError(
                    f"transport failure talking to the gateway ({type(exc).__name__}: {exc})"
                )

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
