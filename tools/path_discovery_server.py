"""
P0 — SDK Path Discovery Diagnostic Server

启动一个最小 HTTP 服务器，记录客户端发送的所有请求特征。
用于在编写 ProviderRouter 代码之前，捕获真实 SDK/Client 的实际 HTTP 行为。

原则：
- 不记录完整 Prompt 内容，只记录 Body 结构
- 不过滤任何请求，记录所有到达的请求
- 输出 JSON 格式，方便后续分析和填入报告

用法：
    python tools/path_discovery_server.py [--port PORT] [--output FILE]

配置客户端 Base URL 指向 http://127.0.0.1:8910 后发送请求即可。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import web

logger = logging.getLogger("path_discovery")


def extract_body_shape(body_text: str) -> dict[str, Any]:
    """提取 Body 结构，不记录完整 Prompt 内容。

    保留：
    - model 字段值
    - 标量字段（bool, int, float）
    - 短字符串（<100 字符）
    - 列表的长度（如 messages_count, tools_count）

    不保留：
    - messages 中每条消息的具体 content
    - 长字符串
    - 二进制内容

    Args:
        body_text: 请求体原始文本。

    Returns:
        描述 Body 结构特征的字典。
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
                # 如果有多条消息，记录最后一条的 role
                if len(value) > 1:
                    shape["last_message_role"] = value[-1].get("role", "unknown")
        elif key == "model":
            shape["model"] = value
        elif key == "tools":
            shape["tools_count"] = len(value)
            if value:
                shape["tool_names"] = [t.get("function", {}).get("name", "?") for t in value[:5]]
        elif key == "functions":
            shape["functions_count"] = len(value)
        elif isinstance(value, (bool, int, float)):
            shape[key] = value
        elif isinstance(value, str) and len(value) < 100:
            shape[key] = value
        elif isinstance(value, list):
            shape[f"{key}_count"] = len(value)
        elif isinstance(value, dict):
            # 记录 dict 的键名和标量值，不记录嵌套内容
            sub = {}
            for sk, sv in value.items():
                if isinstance(sv, (bool, int, float, str)):
                    sub[sk] = sv
                elif isinstance(sv, list):
                    sub[f"{sk}_count"] = len(sv)
                else:
                    sub[sk] = f"<{type(sv).__name__}>"
            shape[key] = sub
        else:
            shape[key] = f"<{type(value).__name__}>"

    return shape


def build_record(request: web.Request, body_text: str, counter: int) -> dict[str, Any]:
    """构建单条请求记录。

    Args:
        request: aiohttp Request 对象。
        body_text: 已解码的请求体文本。
        counter: 请求序号。

    Returns:
        完整的请求记录字典。
    """
    return {
        "#": counter,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "method": request.method,
        "path": request.path,
        "query_string": str(request.query_string) if request.query_string else "",
        "headers": {
            k: ("***" if k.lower() in ("x-api-key", "authorization", "cookie") else v)
            for k, v in request.headers.items()
        },
        "body_shape": extract_body_shape(body_text),
    }


def make_handler(output_file: Path | None):
    """创建请求处理闭包（携带计数器和输出文件引用）。

    Args:
        output_file: 可选 JSON 输出文件路径。

    Returns:
        async handler 函数。
    """
    counter = 0
    records: list[dict[str, Any]] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        nonlocal counter
        counter += 1

        # 读取请求体
        try:
            body_bytes = await request.read()
            body_text = body_bytes.decode("utf-8", errors="replace")
        except Exception:
            body_text = "<read error>"

        record = build_record(request, body_text, counter)

        # 控制台输出
        separator = "=" * 72
        print(f"\n{separator}")
        print(f"  Request #{record['#']}  —  {record['timestamp']}")
        print(f"  {record['method']} {record['path']}{'?' + record['query_string'] if record['query_string'] else ''}")
        print(f"{separator}")
        print(json.dumps(record, indent=2, ensure_ascii=False, default=str))

        records.append(record)

        # 写入输出文件（每条记录后实时写入，防止意外中断丢失数据）
        if output_file:
            try:
                output_file.write_text(
                    json.dumps(records, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
            except Exception as e:
                logger.warning("写入输出文件失败: %s", e)

        # 返回简单响应 — 客户端不需要真实响应，只需要看到请求特征
        content_type = request.headers.get("Content-Type", "")
        return web.Response(
            status=200,
            text=json.dumps({
                "id": f"discovery-{counter:04d}",
                "object": "chat.completion",
                "created": 0,
                "model": record["body_shape"].get("model", "unknown"),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "[Discovery Server — 此响应非真实 API 返回]",
                    },
                    "finish_reason": "stop",
                }],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }, ensure_ascii=False),
            content_type="application/json",
        )

    return handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P0 SDK Path Discovery Diagnostic Server",
    )
    parser.add_argument(
        "--port", type=int, default=8910,
        help="监听端口 (默认: 8910)",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="绑定地址 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="JSON 输出文件路径 (默认: 仅控制台输出)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 72)
    print("  P0 — SDK Path Discovery Diagnostic Server")
    print(f"  监听: http://{args.host}:{args.port}")
    print(f"  输出: {'控制台 + ' + str(args.output) if args.output else '控制台'}")
    print()
    print("  配置客户端 Base URL 指向此地址，然后发送请求。")
    print("  所有请求特征将打印到控制台。")
    print("=" * 72)
    print()
    print("等待请求... (Ctrl+C 停止)")
    print()

    output_file = args.output

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", make_handler(output_file))

    try:
        web.run_app(app, host=args.host, port=args.port, print=None)
    except KeyboardInterrupt:
        print("\n诊断服务器已停止。")


if __name__ == "__main__":
    main()
