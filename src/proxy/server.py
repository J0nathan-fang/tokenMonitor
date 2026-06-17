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
from src.proxy.endpoint_resolver import EndpointResolver
from src.proxy.handler import ProxyHandler
from src.proxy.provider_router import ProviderRouter
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
    """Unified HTTP Server — 同时支持 Gateway 模式和 Proxy 模式。

    在同一端口上处理两种请求格式:
    - Gateway: URL 以 /openai/、/anthropic/ 等前缀开头
    - Proxy: URL 为完整真实 API 地址（通过 HTTP 代理发送）

    Gateway 模式下，通过 ProviderRouter 识别 Provider，
    PathAdapter 归一化路径，EndpointResolver 解析目标 URL，
    然后将请求转发给 ProxyHandler 处理。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8910,
        repository: Repository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the unified server.

        Args:
            host: Bind address.
            port: Bind port (default 8910 for Gateway mode).
            repository: Repository for database access.
            event_bus: Event bus for real-time updates.
        """
        self._host = host
        self._port = port
        self._repository = repository
        self._event_bus = event_bus or EventBus.get_instance()

        # Gateway 组件
        self._router = ProviderRouter()
        self._resolver = EndpointResolver()

        # 数据处理组件
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
        """Handle all incoming requests — Gateway + Proxy 统一入口。

        分流逻辑:
        1. 路径匹配 Gateway 前缀 → Gateway 处理
        2. URL 匹配 AI API 模式 → Proxy 处理（透明代理）
        3. 其他 → 通用转发

        Args:
            request: The incoming aiohttp Request.

        Returns:
            A StreamResponse.
        """
        path = request.path

        # 优先检测 Gateway 请求（不需要构建 url，避免 Host:port 解析失败）
        if self._router.is_gateway_request(path):
            return await self._handle_gateway(request)

        # 以下为 Proxy 模式 — 需要完整 URL
        headers = dict(request.headers)
        raw_url = request.headers.get("Host", "") or request.host
        try:
            url = str(request.url)
        except (ValueError, AttributeError):
            # yarl URL build 可能因 Host:port 格式失败 — 手动构建
            scheme = "https" if request.secure else "http"
            url = f"{scheme}://{raw_url}{path}"
            if request.query_string:
                url += "?" + request.query_string

        # 检测 Proxy 模式的 AI API 请求
        if self._is_ai_api_request(url, headers) and self._handler:
            return await self._handler.handle_request(request)

        # 其他请求 — 通用转发
        return await self._generic_forward(request)

    async def _handle_gateway(self, request: web.Request) -> web.StreamResponse:
        """Handle Gateway mode requests.

        流程:
        1. ProviderRouter 解析路径 → client_type + 归一化 target_path
        2. EndpointResolver 构建目标 URL + 获取 Auth Headers + Provider Identity
        3. 委托 ProxyHandler 转发并解析

        Provider Identity:
        - client_type = Router 检测到的协议类型（如 "openai"）
        - actual_provider = EndpointResolver 中的真实后端（如 "deepseek"）

        Args:
            request: The incoming aiohttp Request.

        Returns:
            A StreamResponse.
        """
        path = request.path
        query_string = str(request.query_string) if request.query_string else ""
        full_path = path + ("?" + query_string if query_string else "")

        # 1. 解析路由 → client_type
        route_result = self._router.resolve_and_normalize(full_path)
        if route_result is None or not route_result.matched:
            logger.warning("Gateway: unknown route '%s'", full_path)
            return web.Response(status=404, text="Unknown provider")

        client_type = route_result.provider

        # 2. 获取 EndpointConfig（含 actual_provider, pricing_version）
        endpoint_config = self._resolver.resolve(client_type)
        if endpoint_config is None:
            logger.error(
                "Gateway: no endpoint config for client_type '%s'",
                client_type,
            )
            return web.Response(status=502, text="Provider not configured")

        actual_provider = endpoint_config.actual_provider
        pricing_version = endpoint_config.pricing_version

        # 3. 构建目标 URL
        target_url = self._resolver.build_target_url(
            client_type,
            route_result.target_path,
        )
        if target_url is None:
            logger.error(
                "Gateway: failed to build target URL for '%s'",
                client_type,
            )
            return web.Response(status=502, text="Provider not configured")

        # 4. 获取 Auth Headers（透传模式）
        client_headers = dict(request.headers)
        auth_value = (
            client_headers.get("Authorization")
            or client_headers.get("authorization")
            or client_headers.get("x-api-key")
            or client_headers.get("X-Api-Key")
            or None
        )
        override_headers = self._resolver.get_api_key_headers(
            client_type,
            auth_value,
        )

        logger.info(
            "Gateway: %s %s → client_type=%s, actual=%s, target=%s",
            request.method, full_path,
            client_type, actual_provider, target_url,
        )

        # 5. 委托 Handler — 传递 Provider Identity
        return await self._handler.handle_request(
            request,
            target_url=target_url,
            override_headers=override_headers,
            client_type=client_type,
            actual_provider=actual_provider,
            pricing_version=pricing_version,
        )

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
