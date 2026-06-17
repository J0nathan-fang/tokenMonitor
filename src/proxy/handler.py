"""
Request handler — intercepts API requests, forwards them, and extracts usage data.

This is the main orchestration point of the proxy layer.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aiohttp import web
from aiohttp.web_request import Request

from src.parser.base import UsageData
from src.parser.registry import ParserRegistry
from src.proxy.forwarder import RequestForwarder
from src.proxy.sse_handler import SSEHandler
from src.statistics.calculator import CostCalculator
from src.statistics.engine import StatisticsEngine

logger = logging.getLogger("token_monitor.proxy.handler")


class ProxyHandler:
    """Handles intercepted API requests.

    Orchestrates:
    1. Forward request to real API
    2. For non-stream: parse usage from response body
    3. For stream: relay SSE chunks, extract usage from final chunk
    4. Record usage via StatisticsEngine
    """

    def __init__(
        self,
        parser_registry: ParserRegistry,
        engine: StatisticsEngine,
        calculator: CostCalculator,
    ) -> None:
        """Initialize the proxy handler.

        Args:
            parser_registry: Parser registry for auto-detection.
            engine: Statistics engine for recording usage.
            calculator: Cost calculator.
        """
        self._registry = parser_registry
        self._engine = engine
        self._calculator = calculator
        self._forwarder = RequestForwarder()
        self._sse_handler = SSEHandler(parser_registry)

    async def handle_request(
        self,
        request: Request,
        target_url: str | None = None,
        override_headers: dict[str, str] | None = None,
        client_type: str = "",
        actual_provider: str = "",
        pricing_version: str = "",
    ) -> web.StreamResponse:
        """Handle an incoming proxy or gateway request.

        This is the main entry point called by the proxy server.

        Args:
            request: The aiohttp Request object.
            target_url: (Gateway mode) Override the upstream URL. If None,
                        uses the original request URL (Proxy mode).
            override_headers: (Gateway mode) Headers to override/add before
                              forwarding. Used for Auth header transformation.
            client_type: SDK/Protocol type (e.g. "openai").
            actual_provider: Real backend API provider (e.g. "deepseek").
            pricing_version: Pricing snapshot identifier.

        Returns:
            A StreamResponse to send back to the client.
        """
        # Read request body
        request_body = await request.read()
        url = target_url if target_url else str(request.url)
        headers = dict(request.headers)

        # Merge override headers (Gateway mode auth transformation)
        if override_headers:
            headers.update(override_headers)
            logger.debug("Gateway: merged %d override headers", len(override_headers))

        # Provider Identity — attached to request for parser/pipeline use
        # Stored as request attributes for downstream access
        request["client_type"] = client_type
        request["actual_provider"] = actual_provider
        request["pricing_version"] = pricing_version

        logger.debug("Handler request: %s %s (client=%s, actual=%s)",
                     request.method, url, client_type, actual_provider)

        # Determine usage source — check stream_options.include_usage
        request["usage_source"] = self._determine_usage_source(request_body)
        if request["usage_source"] == "token_counter_fallback":
            logger.warning(
                "[Streaming Fallback] stream=true without include_usage "
                "— Usage unavailable in stream response"
            )

        # Detect if this is a streaming request
        is_streaming = self._is_stream_request(request_body, headers)

        if is_streaming:
            return await self._handle_stream(request, url, headers, request_body)
        else:
            return await self._handle_regular(request, url, headers, request_body)

    @staticmethod
    def _determine_usage_source(body: bytes) -> str:
        """Determine the usage source for a request.

        Checks stream_options.include_usage flag.

        Args:
            body: Request body bytes.

        Returns:
            "api" if usage will come from API response,
            "token_counter_fallback" if streaming without include_usage.
        """
        if not body:
            return "api"
        import json
        try:
            req = json.loads(body)
            if req.get("stream", False):
                stream_options = req.get("stream_options", {})
                if isinstance(stream_options, dict):
                    if not stream_options.get("include_usage", False):
                        return "token_counter_fallback"
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return "api"

    async def _handle_regular(
        self,
        request: Request,
        url: str,
        headers: dict[str, str],
        request_body: bytes,
    ) -> web.StreamResponse:
        """Handle a non-streaming request.

        Args:
            request: The aiohttp Request.
            url: Target URL.
            headers: Request headers.
            request_body: Request body bytes.

        Returns:
            StreamResponse with the API response.
        """
        try:
            response, latency_ms = await self._forwarder.forward(
                method=request.method,
                url=url,
                headers=headers,
                body=request_body,
            )
        except Exception as e:
            logger.error("Forward request failed: %s", e, exc_info=True)
            return web.Response(status=502, text="Proxy forward failed")

        # Read response body
        response_body = response.content

        # Parse usage
        start_parse = time.perf_counter()
        usage = self._registry.parse_response(
            response_body=response_body,
            url=url,
            headers=headers,
            request_body=request_body,
            status_code=response.status_code,
        )
        parse_latency = (time.perf_counter() - start_parse) * 1000

        if usage:
            usage.latency_ms = latency_ms + parse_latency
            usage.endpoint = url
            # Inject Provider Identity from Gateway metadata
            usage.client_type = request.get("client_type", "")
            usage.actual_provider = request.get("actual_provider", "")
            usage.pricing_version = request.get("pricing_version", "")
            usage.usage_source = request.get("usage_source", "api")

        # Record statistics
        if usage and usage.is_valid:
            try:
                self._engine.record(usage)
            except Exception as e:
                logger.error("Failed to record usage: %s", e, exc_info=True)

        # Build response
        resp = web.StreamResponse(status=response.status_code)
        for key, value in response.headers.items():
            if key.lower() not in ("transfer-encoding", "content-encoding"):
                resp.headers[key] = value

        await resp.prepare(request)
        await resp.write(response_body)
        await resp.write_eof()

        return resp

    async def _handle_stream(
        self,
        request: Request,
        url: str,
        headers: dict[str, str],
        request_body: bytes,
    ) -> web.StreamResponse:
        """Handle a streaming (SSE) request.

        Args:
            request: The aiohttp Request.
            url: Target URL.
            headers: Request headers.
            request_body: Request body bytes.

        Returns:
            StreamResponse that relays the SSE stream.
        """
        try:
            byte_iter, _ = await self._forwarder.forward_stream(
                method=request.method,
                url=url,
                headers=headers,
                body=request_body,
            )
        except Exception as e:
            logger.error("Forward stream failed: %s", e, exc_info=True)
            return web.Response(status=502, text="Proxy stream forward failed")

        # Process SSE stream
        relay_iter, _ = await self._sse_handler.process_stream(
            source=byte_iter,
            url=url,
            request_headers=headers,
            request_body=request_body,
        )

        # Build streaming response
        resp = web.StreamResponse(status=200)
        resp.headers["Content-Type"] = "text/event-stream"
        resp.headers["Cache-Control"] = "no-cache"
        resp.headers["Connection"] = "keep-alive"

        await resp.prepare(request)

        total_bytes = 0
        try:
            async for chunk in relay_iter:
                total_bytes += len(chunk)
                await resp.write(chunk)
        except Exception as e:
            logger.error("Stream relay error: %s", e, exc_info=True)
        finally:
            await resp.write_eof()

        # Extract usage from SSE handler after stream completes
        # The _SSERelayGenerator exposes usage via .usage property
        if hasattr(relay_iter, "usage"):
            usage = relay_iter.usage
            if usage and usage.is_valid:
                usage.endpoint = url
                # Inject Provider Identity from Gateway metadata
                usage.client_type = request.get("client_type", "")
                usage.actual_provider = request.get("actual_provider", "")
                usage.pricing_version = request.get("pricing_version", "")
                usage.usage_source = request.get("usage_source", "api")
                try:
                    self._engine.record(usage)
                except Exception as e:
                    logger.error("Failed to record stream usage: %s", e, exc_info=True)

        logger.debug("Stream complete: %d bytes relayed", total_bytes)
        return resp

    def _is_stream_request(self, body: bytes, headers: dict[str, str]) -> bool:
        """Detect if a request is asking for streaming.

        Also checks for stream_options.include_usage and sets
        usage_source on the request object for downstream pipeline use.

        Args:
            body: Request body bytes.
            headers: Request headers.

        Returns:
            True if this is a streaming request.
        """
        # Check request body for stream flag
        if body:
            import json
            try:
                req = json.loads(body)
                if req.get("stream", False):
                    # Streaming Usage Fallback detection
                    stream_options = req.get("stream_options", {})
                    include_usage = stream_options.get("include_usage", False) if isinstance(stream_options, dict) else False
                    if not include_usage:
                        logger.warning(
                            "[Streaming Fallback] stream=true but stream_options.include_usage "
                            "not set — Usage unavailable in stream response, "
                            "TokenCounter fallback will be used"
                        )
                    return True
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # Check accept header
        accept = headers.get("accept", headers.get("Accept", ""))
        if "text/event-stream" in accept:
            return True

        return False

    async def close(self) -> None:
        """Close the forwarder and release resources."""
        await self._forwarder.close()
