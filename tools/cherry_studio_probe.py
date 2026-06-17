"""
M2.1 Phase 1 — Cherry Studio Request Discovery Probe

透明代理：捕获 Cherry Studio 实际 HTTP 请求特征，转发到 Gateway。

功能：
- 记录 Method, Path, Query String, Headers（API Key 脱敏）
- 记录 Body Shape（model, messages_count, stream, temperature 等）
- 禁止记录 Prompt 内容、API Key 明文
- 转发到 TokenMonitor Gateway → DeepSeek API（Cherry Studio 获得真实响应）
- 支持 Non-Streaming 和 Streaming（SSE 中继）

用法：
    python tools/cherry_studio_probe.py [--port PORT] [--gateway URL]

Cherry Studio 配置:
    Provider Type: OpenAI Compatible
    Base URL: http://127.0.0.1:8911/openai/v1
    API Key: 任意值（Probe 不做认证）
    Model: deepseek-v4-flash

输出:
    docs/cherry_studio_discovery_data.json — 原始捕获数据
    控制台 — 实时请求详情
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from aiohttp import web

logger = logging.getLogger("cherry_studio_probe")

# ── 项目根路径 ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 请求记录存储 ────────────────────────────────────────
_records: list[dict[str, Any]] = []
_counter: int = 0
_gateway_url: str = "http://127.0.0.1:8910"
_output_file: Path | None = None
_inject_api_key: str | None = None  # 注入真实 API Key（从环境变量读取）
_direct_url: str | None = None      # Phase 1: 直连 DeepSeek（跳过 Gateway）


# ═══════════════════════════════════════════════════════════════════
# 路径归一化（Direct 模式）
# ═══════════════════════════════════════════════════════════════════

def _normalize_direct_path(path: str) -> str:
    """Direct 模式下归一化路径（模拟 PathAdapter 行为）。

    Cherry Studio 可能发送的路径变体:
    - /openai/v1/chat/completions  → 剥离 /openai → /v1/chat/completions
    - /v1/chat/completions         → 直接使用
    - /chat/completions            → 补 /v1 → /v1/chat/completions
    - /openai/chat/completions     → 剥离 /openai，补 /v1 → /v1/chat/completions
    """
    result = path

    # 1. 剥离 /openai 前缀
    if result.startswith("/openai/"):
        result = result[len("/openai"):]
    elif result == "/openai":
        result = "/"

    # 2. 确保 /v1/ 前缀
    if not result.startswith("/v1/") and result != "/v1":
        # 避免双 /v1/v1/
        if result.startswith("/v1"):
            result = "/v1/" + result[len("/v1"):].lstrip("/")
        else:
            result = "/v1" + result

    # 3. 去重双 /v1
    while "/v1/v1/" in result:
        result = result.replace("/v1/v1/", "/v1/")

    return result


# ═══════════════════════════════════════════════════════════════════
# Body Shape 提取（不记录 Prompt 内容）
# ═══════════════════════════════════════════════════════════════════

def extract_body_shape(body_text: str) -> dict[str, Any]:
    """提取请求体结构特征，不记录内容。

    保留字段:
    - model
    - stream, temperature, top_p, max_tokens 等标量参数
    - messages_count, first_message_role
    - stream_options (include_usage 等)
    - response_format type

    禁止记录:
    - message content（具体对话内容）
    - 超过 50 字符的字符串值
    """
    try:
        body: dict[str, Any] = json.loads(body_text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"raw_preview": body_text[:200]}

    shape: dict[str, Any] = {}
    for key, value in body.items():
        if key == "messages":
            shape["messages_count"] = len(value)
            if value:
                shape["first_message_role"] = value[0].get("role", "unknown")
                if len(value) > 1:
                    shape["last_message_role"] = value[-1].get("role", "unknown")
        elif key == "model":
            shape["model"] = value
        elif key == "tools":
            shape["tools_count"] = len(value)
            if value:
                names = [t.get("function", {}).get("name", "?") for t in value[:5]]
                shape["tool_names"] = names
        elif isinstance(value, (bool, int, float)):
            shape[key] = value
        elif isinstance(value, str) and len(value) < 50:
            shape[key] = value
        elif isinstance(value, list):
            shape[f"{key}_count"] = len(value)
        elif isinstance(value, dict):
            sub = {}
            for sk, sv in value.items():
                if isinstance(sv, (bool, int, float, str)):
                    sub[sk] = sv if (isinstance(sv, str) and len(sv) < 50) else sv
                elif isinstance(sv, list):
                    sub[f"{sk}_count"] = len(sv)
                else:
                    sub[sk] = f"<{type(sv).__name__}>"
            shape[key] = sub
        else:
            shape[key] = f"<{type(value).__name__}>"

    return shape


# ═══════════════════════════════════════════════════════════════════
# Header 脱敏
# ═══════════════════════════════════════════════════════════════════

SENSITIVE_HEADERS = {
    "authorization", "x-api-key", "api-key",
    "cookie", "set-cookie", "x-auth-token",
}


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    """脱敏敏感 Header 值。"""
    masked = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADERS:
            # 保留前缀 + 脱敏值
            if " " in v:
                prefix, _, suffix = v.partition(" ")
                masked[k] = f"{prefix} {suffix[:4]}***{suffix[-4:] if len(suffix) > 6 else ''}"
            else:
                masked[k] = v[:4] + "***" + (v[-4:] if len(v) > 6 else "")
        else:
            masked[k] = v
    return masked


# ═══════════════════════════════════════════════════════════════════
# 请求处理
# ═══════════════════════════════════════════════════════════════════

async def handle_request(request: web.Request) -> web.StreamResponse:
    """捕获 Cherry Studio 请求，转发到 Gateway。"""
    global _counter
    _counter += 1

    # 读取请求体
    body_bytes = await request.read()
    try:
        body_text = body_bytes.decode("utf-8", errors="replace")
    except Exception:
        body_text = "<read error>"

    # 构建记录
    record = {
        "#": _counter,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "method": request.method,
        "path": request.path,
        "query_string": str(request.query_string) if request.query_string else "",
        "headers": mask_headers(dict(request.headers)),
        "body_shape": extract_body_shape(body_text),
    }

    # 控制台输出
    separator = "─" * 60
    print(f"\n{separator}")
    print(f"  Request #{record['#']} — {record['timestamp']}")
    print(f"  {record['method']} {record['path']}"
          f"{'?' + record['query_string'] if record['query_string'] else ''}")
    print(f"{separator}")
    print(f"  Model:       {record['body_shape'].get('model', '?')}")
    print(f"  Messages:    {record['body_shape'].get('messages_count', '?')}")
    print(f"  Stream:      {record['body_shape'].get('stream', False)}")
    print(f"  Temperature: {record['body_shape'].get('temperature', 'N/A')}")
    stream_opts = record['body_shape'].get('stream_options', {})
    if stream_opts:
        print(f"  Stream Opts: {stream_opts}")
    print(f"  Headers:")
    for k, v in record["headers"].items():
        if k.lower() not in ("host", "accept", "accept-encoding",
                             "content-type", "content-length", "user-agent",
                             "connection", "accept-charset"):
            print(f"    {k}: {v}")

    _records.append(record)
    _save_records()

    # 构建转发目标 URL
    request_path = request.path
    if _direct_url:
        # Phase 1: 直连 DeepSeek API — 需要路径归一化
        # Cherry Studio Base URL: http://127.0.0.1:8911/openai/v1
        # Cherry Studio 实际请求路径可能是:
        #   A) /openai/v1/chat/completions (含前缀 — 需剥离 /openai)
        #   B) /v1/chat/completions         (无前缀 — 直接使用)
        #   C) /chat/completions            (仅端点 — 需补 /v1)
        target_path = _normalize_direct_path(request_path)
        target_url = _direct_url.rstrip("/") + target_path
        record["direct_target_path"] = target_path  # 记录归一化后的路径
    else:
        # Phase 2: 经 Gateway 转发（Gateway 自行处理路径归一化）
        target_url = _gateway_url.rstrip("/") + request_path

    if request.query_string:
        target_url += "?" + request.query_string

    # 检测是否为 Streaming 请求
    is_stream = record["body_shape"].get("stream", False)

    # 准备转发 headers（移除 hop-by-hop）
    forward_headers = dict(request.headers)
    for h in list(forward_headers.keys()):
        if h.lower() in ("host", "transfer-encoding", "connection", "keep-alive"):
            del forward_headers[h]

    # 注入真实 API Key — Cherry Studio 用任意值，Probe 注入真实 Key
    if _inject_api_key:
        forward_headers["Authorization"] = f"Bearer {_inject_api_key}"

    t_start = time.perf_counter()

    if is_stream:
        return await _forward_stream(
            request, target_url, forward_headers, body_bytes, record, t_start,
        )
    else:
        return await _forward_regular(
            request, target_url, forward_headers, body_bytes, record, t_start,
        )


async def _forward_regular(
    request: web.Request,
    url: str,
    headers: dict[str, str],
    body: bytes,
    record: dict[str, Any],
    t_start: float,
) -> web.StreamResponse:
    """转发 Non-Streaming 请求。"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
            )
        except Exception as e:
            print(f"  ✗ Gateway forward failed: {e}")
            return web.Response(status=502, text=f"Gateway error: {e}")

    latency = (time.perf_counter() - t_start) * 1000
    record["gateway_status"] = resp.status_code
    record["latency_ms"] = round(latency, 1)
    print(f"  Response: {resp.status_code} ({latency:.0f}ms)")

    # 返回给 Cherry Studio
    response = web.StreamResponse(status=resp.status_code)
    for key, value in resp.headers.items():
        if key.lower() not in ("transfer-encoding", "content-encoding"):
            response.headers[key] = value
    await response.prepare(request)
    await response.write(resp.content)
    await response.write_eof()
    return response


async def _forward_stream(
    request: web.Request,
    url: str,
    headers: dict[str, str],
    body: bytes,
    record: dict[str, Any],
    t_start: float,
) -> web.StreamResponse:
    """转发 Streaming (SSE) 请求。"""
    chunk_count = 0
    total_bytes = 0

    resp = web.StreamResponse(status=200)
    resp.headers["Content-Type"] = "text/event-stream"
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Connection"] = "keep-alive"
    await resp.prepare(request)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
            ) as stream_resp:
                if stream_resp.status_code != 200:
                    # 非 200 响应 — 读取全部返回
                    content = await stream_resp.aread()
                    record["gateway_status"] = stream_resp.status_code
                    await resp.write(content)
                    await resp.write_eof()
                    return resp

                async for chunk in stream_resp.aiter_bytes():
                    chunk_count += 1
                    total_bytes += len(chunk)
                    await resp.write(chunk)
    except Exception as e:
        print(f"  ✗ Stream forward failed: {e}")
        await resp.write_eof()
        return resp

    await resp.write_eof()

    latency = (time.perf_counter() - t_start) * 1000
    record["gateway_status"] = 200
    record["latency_ms"] = round(latency, 1)
    record["stream_chunks"] = chunk_count
    record["stream_bytes"] = total_bytes
    print(f"  Stream: {chunk_count} chunks, {total_bytes} bytes ({latency:.0f}ms)")

    return resp


# ═══════════════════════════════════════════════════════════════════
# 持久化
# ═══════════════════════════════════════════════════════════════════

def _save_records() -> None:
    """实时写入 JSON 文件（防止意外中断丢失数据）。"""
    if _output_file:
        try:
            _output_file.write_text(
                json.dumps(_records, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("写入输出文件失败: %s", e)


# ═══════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M2.1 Cherry Studio Request Discovery Probe",
    )
    parser.add_argument(
        "--port", type=int, default=8911,
        help="监听端口 (默认: 8911)",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="绑定地址 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--gateway", type=str, default="http://127.0.0.1:8910",
        help="Gateway 地址 (默认: http://127.0.0.1:8910)",
    )
    parser.add_argument(
        "--direct", type=str, default=None,
        help="Phase 1 直连模式: 跳过 Gateway，直接转发到指定 API Base URL"
             " (如 https://api.deepseek.com)",
    )
    parser.add_argument(
        "--output", type=Path,
        default=PROJECT_ROOT / "docs" / "cherry_studio_discovery_data.json",
        help="输出 JSON 文件路径",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    global _gateway_url, _output_file, _inject_api_key, _direct_url
    _gateway_url = args.gateway
    _output_file = args.output
    _direct_url = args.direct

    # 读取真实 API Key（Probe 注入用）
    _inject_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not _inject_api_key:
        print("⚠️  DEEPSEEK_API_KEY 环境变量未设置。")
        print("   Probe 将透传 Cherry Studio 的 Authorization header。")
        print("   如果 Cherry Studio 使用任意 Key，DeepSeek API 将返回 401。")
        print("   设置方式: set DEEPSEEK_API_KEY=sk-xxx")
        print()

    mode = "Direct → DeepSeek" if _direct_url else f"→ Gateway ({args.gateway})"
    print("=" * 60)
    print("  M2.1 — Cherry Studio Request Discovery Probe")
    print("=" * 60)
    print(f"  Probe:   http://{args.host}:{args.port}")
    print(f"  Target:  {_direct_url if _direct_url else args.gateway}")
    print(f"  Mode:    {mode}")
    print(f"  API Key: {'已注入 (DEEPSEEK_API_KEY)' if _inject_api_key else '透传模式'}")
    print(f"  Output:  {args.output}")
    print()
    print("  Cherry Studio 配置:")
    print(f"    Provider Type: OpenAI Compatible")
    print(f"    Base URL:      http://{args.host}:{args.port}/openai/v1")
    if _inject_api_key:
        print(f"    API Key:       任意值（Probe 自动注入真实 Key）")
    else:
        print(f"    API Key:       需填入真实 DeepSeek Key")
    print(f"    Model:         deepseek-v4-flash（或 deepseek-v4-pro）")
    print()
    print("  等待 Cherry Studio 请求... (Ctrl+C 停止)")
    print("=" * 60)

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handle_request)

    try:
        web.run_app(app, host=args.host, port=args.port, print=None)
    except KeyboardInterrupt:
        print(f"\nProbe 停止。共捕获 {_counter} 条请求。")
        if _output_file and _output_file.exists():
            print(f"数据已保存: {_output_file}")


if __name__ == "__main__":
    main()
