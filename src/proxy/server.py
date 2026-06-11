"""
Local HTTP/HTTPS proxy server using aiohttp.

Listens on 127.0.0.1:7890 by default.
Intercepts AI API requests, extracts usage, and forwards to real endpoints.
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import web

from src.core.event_bus import EventBus
from src.parser.registry import ParserRegistry
from src.proxy.handler import ProxyHandler
from src.statistics.calculator import CostCalculator
from src.statistics.engine import StatisticsEngine
from src.database.repository import Repository

logger = logging.getLogger("token_monitor.proxy.server")


# AI API host patterns to intercept
AI_API_PATTERNS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.deepseek.com",
    "openrouter.ai",
    "api.mistral.ai",
    "api.groq.com",
    "api.together.xyz",
    "api.perplexity.ai",
    "api.fireworks.ai",
    "api.x.ai",
    "api.moonshot.cn",
    "api.baichuan-ai.com",
    "api.zhipuai.cn",
    "dashscope.aliyuncs.com",
    "api.minimax.chat",
]


class ProxyServer:
    """Local HTTP proxy server that intercepts AI API calls.

    Transparently forwards requests while extracting token usage data.
    Does NOT modify requests or responses — acts as a transparent monitor.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7890,
        repository: Repository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the proxy server.

        Args:
            host: Bind address.
            port: Bind port.
            repository: Repository for database access.
            event_bus: Event bus for real-time updates.
        """
        self._host = host
        self._port = port
        self._repository = repository
        self._event_bus = event_bus or EventBus.get_instance()

        # Initialize components
        self._parser_registry = ParserRegistry()
        self._calculator = CostCalculator(repository) if repository else None
        self._engine = StatisticsEngine(repository, self._calculator) if repository else None
        self._handler = ProxyHandler(
            self._parser_registry,
            self._engine,
            self._calculator,
        ) if self._engine else None

        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running

    @property
    def port(self) -> int:
        return self._port

    @property
    def host(self) -> str:
        return self._host

    def _is_ai_api_request(self, url: str, headers: dict[str, str]) -> bool:
        """Detect if a request targets a known AI API.

        Args:
            url: Full request URL.
            headers: Request headers.

        Returns:
            True if this looks like an AI API request.
        """
        url_lower = url.lower()
        for pattern in AI_API_PATTERNS:
            if pattern in url_lower:
                return True

        # Check auth header patterns
        auth = headers.get("authorization", headers.get("Authorization", ""))
        auth_lower = auth.lower()
        for keyword in ("openai", "anthropic", "gemini", "deepseek", "openrouter"):
            if keyword in auth_lower:
                return True

        return False

    async def _handle_all(self, request: web.Request) -> web.StreamResponse:
        """Handle all incoming proxy requests.

        Routes AI API requests through the handler for parsing.
        Forwards non-AI requests directly (generic proxy behavior).

        Args:
            request: The incoming aiohttp Request.

        Returns:
            A StreamResponse.
        """
        url = str(request.url)
        headers = dict(request.headers)

        if self._is_ai_api_request(url, headers) and self._handler:
            return await self._handler.handle_request(request)
        else:
            # Generic forward for non-AI requests
            return await self._generic_forward(request)

    async def _generic_forward(self, request: web.Request) -> web.StreamResponse:
        """Generic forward for non-AI requests (basic proxy).

        Args:
            request: The incoming aiohttp Request.

        Returns:
            A StreamResponse.
        """
        import httpx

        body = await request.read()
        headers = dict(request.headers)
        # Remove hop-by-hop headers
        for h in ("transfer-encoding", "connection", "host"):
            headers.pop(h, None)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            try:
                resp = await client.request(
                    method=request.method,
                    url=str(request.url),
                    headers=headers,
                    content=body,
                )
                response = web.StreamResponse(status=resp.status_code)
                for key, value in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "content-encoding"):
                        response.headers[key] = value
                await response.prepare(request)
                await response.write(resp.content)
                await response.write_eof()
                return response
            except Exception as e:
                logger.debug("Generic forward failed: %s", e)
                return web.Response(status=502, text="Proxy error")

    async def start(self) -> None:
        """Start the proxy server."""
        self._app = web.Application()
        self._app.router.add_route("*", "/{tail:.*}", self._handle_all)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()

        self._running = True
        logger.info("Proxy server started on %s:%d", self._host, self._port)

        # Notify event bus
        if self._event_bus:
            self._event_bus.proxy_status_changed.emit(True)

    async def stop(self) -> None:
        """Stop the proxy server."""
        if self._handler:
            await self._handler.close()

        if self._runner:
            await self._runner.cleanup()
            self._runner = None

        self._running = False
        logger.info("Proxy server stopped")

        if self._event_bus:
            self._event_bus.proxy_status_changed.emit(False)
