"""
M2.1 Phase 2 — Gateway Test Server (无 Qt, 仅 Gateway)

启动 TokenMonitor Gateway（带 DeepSeek 配置），用于 Cherry Studio 兼容性测试。

用法:
    python tools/gateway_test_server.py [--port PORT]

Cherry Studio 配置:
    Provider Type: OpenAI Compatible
    Base URL: http://127.0.0.1:8910/openai/v1
    API Key: 填入真实 DeepSeek API Key (Gateway 透传模式)
    Model: deepseek-v4-flash 或 deepseek-v4-pro
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.manager import DatabaseManager
from src.database.repository import Repository
from src.proxy.endpoint_resolver import EndpointConfig
from src.proxy.server import ProxyServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# DeepSeek V4 模型定价
MODEL_PRICING = {
    "deepseek-v4-flash": ("DeepSeek V4 Flash", 0.27, 1.10),
    "deepseek-v4-pro": ("DeepSeek V4 Pro", 0.55, 2.19),
}


def setup_gateway(port: int) -> tuple[ProxyServer, DatabaseManager, Repository, str]:
    """创建并配置 Gateway（DeepSeek 作为 OpenAI Compatible 后端）。"""
    # 临时数据库
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="gateway_test_")
    os.close(fd)

    db = DatabaseManager(db_path)
    db.initialize_schema()
    repo = Repository(db)

    # 写入模型定价
    for model_name, (display, inp, out) in MODEL_PRICING.items():
        repo.insert_model({
            "provider": "deepseek",
            "model_name": model_name,
            "display_name": display,
            "input_price": inp,
            "output_price": out,
            "currency": "USD",
            "enabled": 1,
        })

    # 创建 Gateway 服务器
    server = ProxyServer(host="127.0.0.1", port=port, repository=repo)

    # 覆盖 openai 默认配置 → DeepSeek
    server._resolver.register_provider(EndpointConfig(
        provider="openai",
        base_url="https://api.deepseek.com",
        enabled=True,
        api_key_header="Authorization",
        api_key_prefix="Bearer ",
        actual_provider="deepseek",
        pricing_version="2026-06-deepseek",
    ))

    return server, db, repo, db_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gateway Test Server")
    parser.add_argument("--port", type=int, default=8910, help="监听端口")
    args = parser.parse_args()

    print("=" * 60)
    print("  M2.1 Phase 2 — Gateway Test Server")
    print("=" * 60)
    print(f"  Gateway: http://127.0.0.1:{args.port}")
    print(f"  Upstream: https://api.deepseek.com")
    print(f"  Provider: openai → actual=deepseek, pricing=2026-06-deepseek")
    print(f"  Models: deepseek-v4-flash, deepseek-v4-pro")
    print()
    print("  Cherry Studio 配置:")
    print(f"    Base URL:  http://127.0.0.1:{args.port}/openai/v1")
    print(f"    API Key:  填真实的 DeepSeek API Key（Gateway 透传）")
    print(f"    Model:    deepseek-v4-flash")
    print()
    print("  Ctrl+C 停止")
    print("=" * 60)

    server, db, repo, db_path = setup_gateway(args.port)

    async def run() -> None:
        await server.start()
        print(f"\nGateway 已启动 — 等待请求...\n")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            print("\n正在停止 Gateway...")
            await server.stop()
            # 输出统计
            from datetime import date
            today = date.today().isoformat()
            recent = repo.get_recent_requests(limit=50)
            daily = repo.get_daily_stats(today)
            print(f"\n  Session stats:")
            print(f"    Request logs: {len(recent)}")
            print(f"    Daily stats rows: {len(daily)}")
            if recent:
                total_tokens = sum(r.get("total_tokens", 0) for r in recent)
                total_cost = sum(r.get("cost", 0) for r in recent)
                print(f"    Total tokens: {total_tokens}")
                print(f"    Total cost: ${total_cost:.6f}")
            db.close()
            try:
                os.remove(db_path)
            except Exception:
                pass
            print(f"\nGateway 已停止。")

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
