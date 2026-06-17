# SDK Path Discovery Report

> **P0 — Pre-Implementation Phase**
> Status: **✅ 完成** — P0.1 ✅ OpenAI SDK, P0.2 ✅ Cherry Studio, P0.3 ✅ Anthropic SDK

---

## 目标

在编写任何 Gateway 代码之前，通过启动一个简单的 HTTP 诊断服务器，**捕获各客户端/ SDK 实际发送的 HTTP 请求特征**，确定：

1. 客户端实际请求的完整路径是什么？
2. 客户端实际发送了哪些 Headers（特别是 Auth、Content-Type、stream 标志）？
3. 客户端 Body 的结构特征（model 字段格式、stream 标志、include_usage 等）？
4. 客户端如何处理 Base URL 配置？

**原则：**
- ❌ 不基于 SDK 文档猜测
- ❌ 不基于源码阅读推断
- ✅ 必须通过真实 HTTP 请求验证
- ⚠️ **不记录完整 Prompt 内容，不记录用户隐私数据，只记录结构**

---

## 方法

### 诊断服务器

在本地启动一个最小化的 HTTP 服务器，记录所有请求信息：

```python
# tools/path_discovery_server.py（诊断工具，非正式代码）
import json
from aiohttp import web

def extract_body_shape(body_text: str) -> dict:
    """提取 Body 结构，不记录完整 Prompt 内容。"""
    try:
        body = json.loads(body_text)
        shape = {}
        for key, value in body.items():
            if key == "messages":
                # 只记录消息数量和第一条消息的 role，不记录内容
                shape["messages_count"] = len(value)
                if value:
                    shape["first_message_role"] = value[0].get("role", "unknown")
            elif key == "model":
                shape["model"] = value
            elif isinstance(value, (bool, int, float)):
                shape[key] = value
            elif isinstance(value, str) and len(value) < 100:
                shape[key] = value
            elif isinstance(value, list):
                shape[f"{key}_count"] = len(value)
            else:
                shape[key] = f"<{type(value).__name__}>"
        return shape
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"raw_preview": body_text[:200]}

async def handler(request):
    body_bytes = await request.read()
    body_text = body_bytes.decode("utf-8", errors="replace")

    info = {
        "method": request.method,
        "path": request.path,
        "query_string": str(request.query_string) if request.query_string else "",
        "headers": dict(request.headers),
        "body_shape": extract_body_shape(body_text),
    }
    print(json.dumps(info, indent=2, ensure_ascii=False))
    print("---")
    return web.Response(text="OK")

app = web.Application()
app.router.add_route("*", "/{tail:.*}", handler)
web.run_app(app, host="127.0.0.1", port=8910)
```

### 验证清单

对每个客户端执行以下步骤：

1. 启动诊断服务器（`python tools/path_discovery_server.py`）
2. 配置客户端指向 `http://127.0.0.1:8910`
3. 发送一个最简单的请求（非流式）
4. 发送一个流式请求（stream=True）
5. 记录服务器打印的完整 request 特征
6. 截图保存

### 输出格式

每个客户端必须按以下格式记录：

| 字段 | 值 |
|------|-----|
| Client | OpenAI SDK |
| Version | x.x.x |
| Configured Base URL | `http://127.0.0.1:8910/openai/v1` |
| Method | POST |
| Path | `/openai/v1/chat/completions` |
| Headers | `Authorization: Bearer test-key`, `Content-Type: application/json` |
| Query | （空或实际值） |
| Body Shape | `{"model": "gpt-4o-mini", "stream": true, "temperature": 0.7, "messages_count": 1, "first_message_role": "user"}` |
| Notes | stream 标志为 true，include_usage 存在/不存在 |

---

## P0.1 — OpenAI Python SDK

### 测试配置

```python
from openai import OpenAI

# 测试 A: base_url 以 /v1 结尾
client = OpenAI(
    base_url="http://127.0.0.1:8910/openai/v1",
    api_key="test-key",
)
client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "hello"}],
)

# 测试 B: base_url 以 /openai 结尾
client = OpenAI(
    base_url="http://127.0.0.1:8910/openai",
    api_key="test-key",
)
client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "hello"}],
)

# 测试 C: 流式请求
client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "hello"}],
    stream=True,
)
```

### 验证记录

| # | Version | Base URL | Method | Path | Headers (关键) | Query | Body Shape | Notes |
|---|--------|---------|--------|------|---------------|-------|-----------|-------|
| A | 2.30.0 | `.../openai/v1` | POST | `/openai/v1/chat/completions` | `Authorization: Bearer test-key`, `Content-Type: application/json`, `User-Agent: OpenAI/Python 2.30.0`, `X-Stainless-Lang: python`, `X-Stainless-Package-Version: 2.30.0`, `X-Stainless-OS: Windows`, `X-Stainless-Arch: other:amd64`, `X-Stainless-Runtime: CPython`, `X-Stainless-Runtime-Version: 3.11.9`, `X-Stainless-Async: false`, `Accept: application/json` | (空) | `model: "gpt-4o"`, `messages_count: 1`, `first_message_role: "user"` | 非流式。SDK 直接在 base_url 后追加 `/chat/completions`，base_url 包含 `/v1` 则路径也有 `/v1` |
| B | 2.30.0 | `.../openai` | POST | `/openai/chat/completions` | 同上 | (空) | `model: "gpt-4o"`, `messages_count: 1`, `first_message_role: "user"` | ⚠️ **路径无 `/v1`！** 当 base_url=`.../openai` 时，SDK 拼接 `/chat/completions`，不自动补 `/v1`。Gateway 需负责补全 |
| C | 2.30.0 | `.../openai/v1` | POST | `/openai/v1/chat/completions` | 同上 | (空) | `model: "gpt-4o-mini"`, `stream: true`, `messages_count: 1`, `first_message_role: "user"` | 流式。路径与非流式**相同**。`stream` 标志在 Body 中 |
| D | 2.30.0 | `.../openai` | POST | `/openai/chat/completions` | 同上 | (空) | `model: "gpt-4o"`, `stream: true`, `messages_count: 1`, `first_message_role: "user"` | 流式 + 无 `/v1` 双重验证 |
| E | 2.30.0 | `.../openai/v1` | POST | `/openai/v1/chat/completions` | 同上 | (空) | `model: "gpt-4o"`, `stream: true`, `stream_options: {include_usage: true}`, `messages_count: 1`, `first_message_role: "user"` | `stream_options.include_usage` 在 Body 中 |
| F | 2.30.0 | `.../openai` | POST | `/openai/chat/completions` | 同上 | (空) | `model: "gpt-4o"`, `max_tokens: 100`, `temperature: 0.7`, `messages_count: 1`, `first_message_role: "user"` | `max_tokens` 和 `temperature` 在 Body 中，非流式 |

### 关键问题（已解答）

- [x] SDK 在 `base_url` 后追加的路径是 `/chat/completions` 还是 `/v1/chat/completions`？→ **`/chat/completions`**（不自动补 `/v1`）
- [x] SDK 是否自动在 `base_url` 末尾添加 `/`？→ **不会**。base_url 末尾是什么就直接拼什么。
- [x] 流式请求的路径与非流式是否相同？→ **完全相同**。区别仅在 Body 中的 `stream: true`。
- [x] SDK 默认发送哪些 Headers？→ `Authorization: Bearer <key>`、`Content-Type: application/json`、`Accept: application/json`、以及一系列 `X-Stainless-*` 元数据头（Lang, Package-Version, OS, Arch, Runtime, Runtime-Version, Async, retry-count, read-timeout）。**不发送** `x-api-key`。

---

## P0.2 — Cherry Studio

> **状态：✅ VERIFIED** — 2026-06-17，Gateway E2E 验证通过

### 测试 A: OpenAI Compatible Provider

Cherry Studio → 设置 → 模型服务：

| 字段 | 值 |
|------|-----|
| Provider 类型 | OpenAI Compatible |
| API Address | `http://127.0.0.1:8910/openai/v1` |
| API Key | DeepSeek Key (`sk-...`) |

### 验证记录 A

| # | Version | API Address | Method | Path | Headers (关键) | Query | Body Shape | Notes |
|---|--------|------------|--------|------|---------------|-------|-----------|-------|
| A | 1.8.0 | `.../openai/v1` | POST | `/openai/v1/chat/completions` | `Authorization: Bearer <key>`, `x-title: Cherry Studio`, `User-Agent: ...CherryStudio/1.8.0...Electron/40.8.0...`, `http-referer: https://cherry-ai.com`, `Content-Type: application/json` | (空) | `model: "deepseek-v4-flash"`, `messages_count: 1` | 非流式。路径行为与 OpenAI SDK **完全一致** |
| B | 1.8.0 | `.../openai/v1` | POST | `/openai/v1/chat/completions` | 同上 | (空) | `model: "deepseek-v4-flash"`, `stream: true`, `stream_options: {include_usage: true}`, `messages_count: 4` | 流式。路径与非流式相同。`stream_options.include_usage` **已发送** |

### Gateway E2E 验证结果 (2026-06-17)

6 条请求全部成功，4,966 tokens，$0.002296，已验证：
- Router (`/openai` 前缀) ✅
- OpenAIPathAdapter (剥离 `/openai` → `/v1/chat/completions`) ✅
- EndpointResolver (`api.deepseek.com`) ✅
- Auth 透传 ✅
- Usage 解析 (`usage_source=api`) ✅
- Provider Identity (`client_type=openai`, `actual_provider=deepseek`) ✅

### 测试 B: Anthropic Provider

> 待验证（需要 Anthropic API Key 或配置 Anthropic→DeepSeek 路由）

### 关键发现

- [x] Cherry Studio 1.8.0 路径行为与 OpenAI SDK **完全一致**，可直接复用 OpenAIPathAdapter
- [x] 流式与非流式路径相同
- [x] 流式请求**默认发送** `stream_options.include_usage: true` → 不需要 TokenCounter fallback
- [x] Cherry Studio 特有 Headers：`x-title: Cherry Studio`、`http-referer: https://cherry-ai.com`
- [x] **不需要任何 Cherry Studio 特判逻辑** — 现有 Gateway 直接兼容

---

## P0.3 — Anthropic Python SDK

### 测试配置

```python
from anthropic import Anthropic

# 测试 A: 标准 base_url（非流式）
client = Anthropic(
    base_url="http://127.0.0.1:8910/anthropic",
    api_key="test-key",
)
client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=100,
    messages=[{"role": "user", "content": "hello"}],
)

# 测试 B: 流式
with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=100,
    messages=[{"role": "user", "content": "hello"}],
) as stream:
    for text in stream.text_stream:
        pass
```

### 验证记录

| # | Version | Base URL | Method | Path | Headers (关键) | Query | Body Shape | Notes |
|---|--------|---------|--------|------|---------------|-------|-----------|-------|
| A | 0.109.2 | `.../anthropic` | POST | `/anthropic/v1/messages` | `x-api-key: ***`, `anthropic-version: 2023-06-01`, `Content-Type: application/json`, `User-Agent: Anthropic/Python 0.109.2`, `X-Stainless-*` | (空) | `model: "claude-sonnet-4-20250514"`, `max_tokens: 100`, `messages_count: 1`, `first_message_role: "user"` | 非流式。SDK 自动在 base_url 后追加 `/v1/messages` |
| B | 0.109.2 | `.../anthropic` | POST | `/anthropic/v1/messages` | 同上 + `X-Stainless-Helper-Method: stream`, `X-Stainless-Stream-Helper: messages`, `x-stainless-timeout: NOT_GIVEN` | (空) | `model: "claude-sonnet-4-20250514"`, `max_tokens: 100`, `stream: true`, `messages_count: 1`, `first_message_role: "user"` | 流式。路径同非流式。`stream: true` 在 Body 中 |
| C | 0.109.2 | `.../anthropic/v1` | POST | ⚠️ `/anthropic/v1/v1/messages` | 同 A | (空) | 同 A | ⚠️ **Double /v1！** SDK 已内置 `/v1` → 用户不应在 base_url 末尾加 `/v1` |
| D | 0.109.2 | `.../anthropic/v1` | POST | ⚠️ `/anthropic/v1/v1/messages` | 同 B | (空) | 同 B | 流式 + double /v1 |

### 关键问题（已解答）

- [x] SDK 构造的路径是 `/v1/messages` 还是 `/messages`？→ **`/v1/messages`**。SDK 在 base_url 后自动追加 `/v1/messages`
- [x] 不同 SDK 版本是否存在路径差异？→ 未测试多版本（0.109.2 为当前最新稳定版）
- [x] Auth Header 格式？→ **`x-api-key`**（不是 `Authorization: Bearer`！）。与 OpenAI 的 `Authorization: Bearer` 不同
- [x] `anthropic-version` Header 的值？→ **`2023-06-01`**

---

## 汇总结论

基于 2026-06-17 真实抓包数据汇总：

| Client | Version | Base URL | Actual Path Pattern | Body Key Fields | ProviderRouter 需要匹配的模式 |
|--------|---------|---------|-------------------|----------------|---------------------------|
| OpenAI SDK | 2.30.0 | `.../openai/v1` | `/openai/v1/chat/completions` | `model`, `messages`, `stream`, `temperature`, `max_tokens`, `stream_options` | `/openai/v1/*` — 直接透传 |
| OpenAI SDK | 2.30.0 | `.../openai` | `/openai/chat/completions` | 同上 | `/openai/*` — **需补全 /v1 前缀后转发** |
| Cherry Studio (OpenAI Compatible) | 1.8.0 | `.../openai/v1` | `/openai/v1/chat/completions` | `model`, `messages`, `stream`, `stream_options` | `/openai/v1/*` — 与 OpenAI SDK 完全一致，直接复用 OpenAIPathAdapter |
| Cherry Studio (Anthropic) | TBD | `.../anthropic` | Pending | Pending | 待验证 |
| Anthropic SDK | 0.109.2 | `.../anthropic` | `/anthropic/v1/messages` | `model`, `max_tokens`, `messages`, `stream` | `/anthropic/v1/*` — 直接透传 |
| Anthropic SDK | 0.109.2 | `.../anthropic/v1` | ⚠️ `/anthropic/v1/v1/messages` | 同上 | `/anthropic/v1/*` — **检测并处理 double /v1** |

### Router 设计决策

- [x] 确认 ProviderRouter 需要支持的路径变体列表：
  - OpenAI: `/openai/v1/*`（标准）、`/openai/*`（缺失 /v1，需网关补全）
  - Anthropic: `/anthropic/v1/*`（标准）、`/anthropic/v1/v1/*`（double /v1 防御性处理）
- [x] 确认 Anthropic 宽松匹配策略的具体规则：匹配 `/anthropic` 前缀即可，无需精确路径
- [x] 确认是否需要处理 `/v1` 缺失的情况：**是**。OpenAI SDK 在 `base_url=/openai` 时不发送 `/v1`，Gateway 需补全
- [x] 确认 `stream` 标志位置：**请求 Body 中**（`"stream": true`），不在 Header 中
- [x] 确认 `include_usage` 字段是否由各 SDK 默认发送：**否**。需显式传 `stream_options={"include_usage": True}`，字段在 Body 中

### Auth Header 汇总

| Client | Auth Header | 格式 |
|--------|------------|------|
| OpenAI SDK | `Authorization` | `Bearer <key>` |
| Anthropic SDK | `x-api-key` | `<key>` |

### Streaming Usage Fallback

**P0 发现：** `stream_options.include_usage` 不是各 SDK 默认发送的字段。当客户端设置 `stream=true` 但未显式传递 `stream_options={"include_usage": True}` 时，上游 API 的流式响应中**不会包含 `usage` 信息**。

**M1 实现要求：**

网关在检测到以下条件时触发 Fallback：
1. 请求 Body 中 `stream: true`
2. 请求 Body 中**缺少** `stream_options.include_usage`（或 `stream_options` 完全不存在）

**Fallback 逻辑：**
```
if body["stream"] == true and not body.get("stream_options", {}).get("include_usage"):
    log.warning("[Streaming Fallback] Usage unavailable in stream response")
    # 此请求的 Token 统计将使用 TokenCounter 本地估算
    # usage 来源：--, Cost 来源：估算标记 [E]
```

**行为：**
- ✅ 请求仍然正常转发（不影响客户端正常使用）
- ⚠️ 请求日志中标记 `usage_source="token_counter_fallback"`（非精确统计）
- ⚠️ 数据库 `request_logs` 中标记为「估算」而非「精确」
- 仪表盘中显示估算标记

**推荐用户配置：**
```python
# OpenAI SDK — 确保流式响应包含 Usage
client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    stream=True,
    stream_options={"include_usage": True},  # ← 推荐显式设置
)
```

### 路径拼接行为对比

| Client | Base URL 不含 /v1 时 | Base URL 含 /v1 时 | SDK 行为 |
|--------|---------------------|-------------------|----------|
| OpenAI SDK | `/openai/chat/completions` | `/openai/v1/chat/completions` | SDK 直接拼接 `/chat/completions`，不插入 /v1 |
| Anthropic SDK | `/anthropic/v1/messages` | ⚠️ `/anthropic/v1/v1/messages` | SDK 自动追加 `/v1/messages`，用户不应再加 /v1 |

---

**此文档必须在编写 ProviderRouter 代码之前完成并填入真实数据。**
