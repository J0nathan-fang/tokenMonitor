"""
Mock OpenAI Compatible Provider — 用于 M1 集成测试。

模拟 OpenAI Chat Completions API，返回固定 Usage。
支持非流式和流式（SSE）两种模式。

用法:
    python tests/mock_provider.py [--port PORT]

单独启动:
    python tests/mock_provider.py
    监听 http://127.0.0.1:9001

程序化使用:
    from tests.mock_provider import MockProvider
    server = MockProvider(port=9001)
    await server.start()
    # ... 测试 ...
    await server.stop()
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

from aiohttp import web

logger = logging.getLogger("token_monitor.test.mock_provider")

# 固定 Usage — 用于验证 Token 统计准确性
FIXED_USAGE: dict[str, int] = {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
}

# 固定模型名
FIXED_MODEL = "gpt-4o-mock"

# 请求计数器（用于验证请求是否到达）
request_log: list[dict[str, Any]] = []


def build_non_stream_response(body: dict[str, Any]) -> dict[str, Any]:
    """构建非流式 Chat Completion 响应。

    Args:
        body: 请求体（用于提取 model 等信息）。

    Returns:
        OpenAI 格式的 Chat Completion 响应。
    """
    model = body.get("model", FIXED_MODEL)
    return {
        "id": f"chatcmpl-mock-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"[Mock Response] This is a test response from Mock Provider. "
                               f"Model: {model}",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": FIXED_USAGE["prompt_tokens"],
            "completion_tokens": FIXED_USAGE["completion_tokens"],
            "total_tokens": FIXED_USAGE["total_tokens"],
        },
    }


def build_stream_chunks(body: dict[str, Any]) -> list[str]:
    """构建流式 SSE 响应块。

    模拟 OpenAI SSE 流式响应格式，末尾包含 usage 信息。

    Args:
        body: 请求体。

    Returns:
        SSE 格式的字符串列表（每个元素为一个 data: 行）。
    """
    model = body.get("model", FIXED_MODEL)
    chunk_id = f"chatcmpl-mock-stream-{int(time.time())}"

    chunks = [
        # 第一个 chunk — delta role
        'data: {"id":"%s","object":"chat.completion.chunk",'
        '"created":%d,"model":"%s",'
        '"choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}'
        % (chunk_id, int(time.time()), model),
        # 中间 chunk — delta content
        'data: {"id":"%s","object":"chat.completion.chunk",'
        '"created":%d,"model":"%s",'
        '"choices":[{"index":0,"delta":{"content":"[Mock Stream Response] "},"finish_reason":null}]}'
        % (chunk_id, int(time.time()), model),
        'data: {"id":"%s","object":"chat.completion.chunk",'
        '"created":%d,"model":"%s",'
        '"choices":[{"index":0,"delta":{"content":"This is a test "},"finish_reason":null}]}'
        % (chunk_id, int(time.time()), model),
        'data: {"id":"%s","object":"chat.completion.chunk",'
        '"created":%d,"model":"%s",'
        '"choices":[{"index":0,"delta":{"content":"streaming response."},"finish_reason":null}]}'
        % (chunk_id, int(time.time()), model),
        # 最后一个 chunk — finish_reason + usage
        'data: {"id":"%s","object":"chat.completion.chunk",'
        '"created":%d,"model":"%s",'
        '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}],'
        '"usage":{"prompt_tokens":%d,"completion_tokens":%d,"total_tokens":%d}}'
        % (
            chunk_id, int(time.time()), model,
            FIXED_USAGE["prompt_tokens"],
            FIXED_USAGE["completion_tokens"],
            FIXED_USAGE["total_tokens"],
        ),
        # 流结束标志
        "data: [DONE]",
    ]
    return chunks


class MockProvider:
    """Mock OpenAI Compatible API Server。

    模拟以下端点:
    - POST /v1/chat/completions  (非流式 + 流式)
    - POST /chat/completions      (同，用于测试 PathAdapter /v1 补全)

    返回固定 Usage: prompt_tokens=100, completion_tokens=50, total_tokens=150
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9001) -> None:
        self._host = host
        self._port = port
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._running = False
        self._request_count = 0

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def request_count(self) -> int:
        return self._request_count

    async def _handler(self, request: web.Request) -> web.StreamResponse:
        """统一请求处理 — 非流式 + 流式。"""
        self._request_count += 1

        body_bytes = await request.read()
        body_text = body_bytes.decode("utf-8", errors="replace")

        try:
            body: dict[str, Any] = json.loads(body_text)
        except json.JSONDecodeError:
            return web.Response(status=400, text="Invalid JSON")

        # 记录请求
        request_log.append({
            "timestamp": time.time(),
            "method": request.method,
            "path": request.path,
            "headers": dict(request.headers),
            "body": body,
        })
        logger.info(
            "[Mock #%d] %s %s stream=%s model=%s",
            self._request_count,
            request.method,
            request.path,
            body.get("stream", False),
            body.get("model", "unknown"),
        )

        is_streaming = body.get("stream", False)

        if is_streaming:
            # SSE 流式响应
            resp = web.StreamResponse(status=200)
            resp.headers["Content-Type"] = "text/event-stream"
            resp.headers["Cache-Control"] = "no-cache"
            resp.headers["Connection"] = "keep-alive"
            await resp.prepare(request)

            chunks = build_stream_chunks(body)
            for chunk_str in chunks:
                await resp.write((chunk_str + "\n\n").encode("utf-8"))

            await resp.write_eof()
            return resp
        else:
            # 普通 JSON 响应
            response_body = build_non_stream_response(body)
            return web.Response(
                status=200,
                body=json.dumps(response_body, ensure_ascii=False),
                content_type="application/json",
            )

    async def start(self) -> None:
        """启动 Mock Provider 服务器。"""
        self._app = web.Application()

        # 注册路由 — 同时支持 /v1/ 和 / 两种路径
        # (测试 PathAdapter 的 /v1 补全和直接路由)
        async def handler_v1(request):
            return await self._handler(request)

        async def handler_no_v1(request):
            return await self._handler(request)

        # 两种路径变体都注册
        self._app.router.add_route("POST", "/v1/chat/completions", handler_v1)
        self._app.router.add_route("POST", "/chat/completions", handler_no_v1)
        # Health check
        self._app.router.add_route("GET", "/health", lambda r: web.Response(text="OK"))

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()

        self._running = True
        logger.info("Mock Provider started on %s", self.url)

    async def stop(self) -> None:
        """停止 Mock Provider。"""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        self._running = False
        logger.info("Mock Provider stopped (total requests: %d)", self._request_count)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock OpenAI Compatible Provider")
    parser.add_argument("--port", type=int, default=9001, help="监听端口 (默认: 9001)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="绑定地址")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)

    print(f"Mock Provider starting on http://{args.host}:{args.port}")
    print(f"  POST {args.host}:{args.port}/v1/chat/completions  (non-stream + stream)")
    print(f"  POST {args.host}:{args.port}/chat/completions      (without /v1)")
    print()

    app = web.Application()
    server = MockProvider(host=args.host, port=args.port)

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(server.start())
        print("Mock Provider running. Press Ctrl+C to stop.")
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
        loop.run_until_complete(server.stop())


if __name__ == "__main__":
    main()
