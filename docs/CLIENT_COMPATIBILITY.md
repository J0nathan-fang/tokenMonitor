# Client Compatibility Matrix

> 客户端与 TokenMonitor Gateway 的兼容性状态。
> **原则：Evidence First — 仅在真实验证后标记 Verified。**

---

## 状态定义

| 状态 | 含义 |
|------|------|
| **Expected** | 设计支持，尚未实测 |
| **Testing** | 已实现，正在验证中 |
| **Verified** | 真实环境验证通过（需附日期、版本、测试结果） |
| **Unsupported** | 当前架构不支持（含原因） |

---

## 客户端兼容性

| 客户端 | 版本 | 模式 | 状态 | 验证日期 | 备注 |
|--------|------|------|------|---------|------|
| **OpenAI Python SDK** | 2.30.0 | Gateway (`base_url`) | ✅ Verified | 2026-06-17 | 非流式 + 流式，路径变体已处理 |
| **OpenAI Python SDK** | 2.30.0 | Proxy (`HTTP_PROXY`) | ✅ Verified | 2026-06-17 | 透明代理 |
| **Anthropic Python SDK** | 0.109.2 | Gateway (`base_url`) | ✅ Verified | 2026-06-17 | 非流式 + 流式，double /v1 已处理 |
| **DeepSeek Python SDK** | — | Gateway (OpenAI Compatible) | ✅ Verified | 2026-06-17 | 通过 openai client_type 路由到 DeepSeek |
| **Cherry Studio (OpenAI Compatible)** | 1.8.0 | Gateway (Base URL) | ✅ Verified | 2026-06-17 | 路径行为与 OpenAI SDK 一致，Gateway E2E 验证通过 |
| **Cherry Studio (Anthropic)** | 1.8.0 | Gateway (Base URL) | Expected | — | 待 Discovery |
| **Claude Code** | — | Proxy (`HTTP_PROXY`) | ❌ Unsupported | — | 不支持 CONNECT 隧道/TLS MITM |
| **Cursor** | — | Proxy (`HTTP_PROXY`) | Expected | — | 待验证 |
| **Continue** | — | Proxy (`HTTP_PROXY`) | Expected | — | 待验证 |
| **Open WebUI** | — | Gateway (Base URL) | Expected | — | 待验证 |

---

## 配置参考

### Cherry Studio

| 字段 | 值 |
|------|-----|
| Provider Type | OpenAI Compatible |
| Base URL | `http://127.0.0.1:8910/openai/v1` |
| API Key | 你的真实 API Key（透传模式） |

### OpenAI Python SDK

```python
from openai import OpenAI
client = OpenAI(
    base_url="http://127.0.0.1:8910/openai/v1",
    api_key="sk-xxx",
)
```

### Anthropic Python SDK

```python
from anthropic import Anthropic
client = Anthropic(
    base_url="http://127.0.0.1:8910/anthropic",
    api_key="sk-ant-xxx",
)
```
