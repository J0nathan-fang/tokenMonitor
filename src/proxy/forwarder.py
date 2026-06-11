"""
Request forwarder — forwards client requests to real AI API endpoints.

Uses httpx for async HTTP with connection pooling.
Supports both regular and streaming responses.
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator

import httpx

logger = logging.getLogger("token_monitor.proxy.forwarder")

# Headers to strip before forwarding (hop-by-hop headers)
HOP_BY_HOP_HEADERS = {
    "transfer-encoding",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "upgrade",
    "host",
}


class RequestForwarder:
    """Forwards HTTP requests to their intended destinations via httpx."""

    def __init__(
        self,
        timeout: float = 300.0,
        max_connections: int = 50,
    ) -> None:
        """Initialize the forwarder with an httpx client pool.

        Args:
            timeout: Request timeout in seconds.
            max_connections: Maximum concurrent connections.
        """
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._max_connections = max_connections

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx client.

        Returns:
            An httpx.AsyncClient instance.
        """
        if self._client is None:
            limits = httpx.Limits(
                max_connections=self._max_connections,
                max_keepalive_connections=20,
            )
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=limits,
                follow_redirects=False,
            )
            logger.info("HTTPX client created (timeout=%ds, max_conn=%d)",
                        self._timeout, self._max_connections)
        return self._client

    def _filter_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Remove hop-by-hop headers that shouldn't be forwarded.

        Args:
            headers: Original request headers dict.

        Returns:
            Filtered headers dict.
        """
        return {
            k: v
            for k, v in headers.items()
            if k.lower() not in HOP_BY_HOP_HEADERS
        }

    async def forward(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
    ) -> tuple[httpx.Response, float]:
        """Forward a non-streaming request.

        Args:
            method: HTTP method.
            url: Target URL.
            headers: Request headers.
            body: Request body bytes.

        Returns:
            Tuple of (httpx.Response, latency_ms).
        """
        client = await self._get_client()
        filtered_headers = self._filter_headers(headers)

        start = time.perf_counter()
        response = await client.request(
            method=method,
            url=url,
            headers=filtered_headers,
            content=body,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        logger.debug(
            "Forwarded %s %s → %d (%.0fms)",
            method, url, response.status_code, latency_ms,
        )
        return response, latency_ms

    async def forward_stream(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
    ) -> tuple[AsyncIterator[bytes], float]:
        """Forward a streaming request.

        Args:
            method: HTTP method.
            url: Target URL.
            headers: Request headers.
            body: Request body bytes.

        Returns:
            Tuple of (async byte iterator, latency_ms).
        """
        client = await self._get_client()
        filtered_headers = self._filter_headers(headers)

        start = time.perf_counter()
        response = await client.send(
            client.build_request(
                method=method,
                url=url,
                headers=filtered_headers,
                content=body,
            ),
            stream=True,
        )
        connect_latency = (time.perf_counter() - start) * 1000

        async def byte_iterator():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()

        return byte_iterator(), connect_latency

    async def close(self) -> None:
        """Close the httpx client and release connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("HTTPX client closed")
