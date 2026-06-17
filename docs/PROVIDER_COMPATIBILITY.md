# Provider Compatibility Matrix

> **TokenMonitor — Unified AI Gateway + Token Analytics Platform**
> Last updated: 2026-06-17
> Status: **Pending Implementation** — 所有兼容性状态均为预期，待真实验证后更新

---

## 状态说明

| 状态 | 含义 |
|------|------|
| **Expected** | 设计支持，尚未测试 |
| **Testing** | 已实现，正在验证 |
| **Verified** | 真实环境验证通过（需附日期、版本、测试结果） |

> **重要约束：** 只有在完成真实联调测试后，状态才能更新为 Verified。当前所有条目均为 Expected。

---

## 支持的 Provider（Gateway 模式）

| # | Provider | Gateway 前缀 | 目标 Base URL | 优先级 | 开发阶段 | 状态 |
|---|----------|-------------|--------------|--------|---------|------|
| 1 | **OpenAI** | `/openai/` | `https://api.openai.com` | **P0** | M1（当前里程碑） | Expected |
| 2 | **Anthropic** | `/anthropic/` | `https://api.anthropic.com` | **P0** | M2 | Expected |
| 3 | **Gemini** | `/gemini/` | `https://generativelanguage.googleapis.com` | **P1** | M3 | Expected |
| 4 | **DeepSeek** | `/deepseek/` | `https://api.deepseek.com` | P1 | M3 | Expected |
| 5 | **OpenRouter** | `/openrouter/` | `https://openrouter.ai/api` | P1 | M3 | Expected |
| 6 | **CC-Switch** | `/ccswitch/` | 可配置 | P1 | M3 | Expected |

**优先级说明：**
- **P0 (M1)：** 第一里程碑，OpenAI Gateway E2E 验证通过后启动其他 Provider
- **P0 (M2)：** M1 完成后立即启动
- **P1 (M3)：** Gemini 复杂度较高（路径结构特殊、Usage 字段不同、Streaming 格式不同），延后到 M3
| 7 | **Mistral** | `/mistral/` | `https://api.mistral.ai` | OpenAI-compat | `Authorization: Bearer ...` | Planned |
| 8 | **Groq** | `/groq/` | `https://api.groq.com` | OpenAI-compat | `Authorization: Bearer ...` | Planned |
| 9 | **xAI (Grok)** | `/xai/` | `https://api.x.ai` | OpenAI-compat | `Authorization: Bearer ...` | Planned |

---

## API 覆盖范围（按 Provider）

### OpenAI（`/openai/`）

| API 端点 | Gateway URL | Streaming | Usage 解析 | 状态 |
|---------|------------|-----------|-----------|------|
| Chat Completions | `POST /openai/v1/chat/completions` | Expected | Expected | Pending Validation |
| Responses API | `POST /openai/v1/responses` | Expected | Expected | Pending Validation |
| Completions (Legacy) | `POST /openai/v1/completions` | Expected | Expected | Pending Validation |
| Embeddings | `POST /openai/v1/embeddings` | N/A | N/A（无 Token 统计） | Pending Validation |
| Models List | `GET /openai/v1/models` | N/A | N/A | Pending Validation |

### Anthropic（`/anthropic/`）

| API 端点 | Gateway URL | Streaming | Usage 解析 | 状态 |
|---------|------------|-----------|-----------|------|
| Messages | `POST /anthropic/v1/messages` | Expected | Expected（含 cache 统计） | Pending Validation |
| Messages (非流式) | `POST /anthropic/v1/messages` | N/A | Expected（含 cache 统计） | Pending Validation |

### DeepSeek（`/deepseek/`）

| API 端点 | Gateway URL | Streaming | Usage 解析 | 状态 |
|---------|------------|-----------|-----------|------|
| Chat Completions | `POST /deepseek/v1/chat/completions` | Expected | Expected（OpenAI 格式） | Pending Validation |

### Gemini（`/gemini/`）— P1

| API 端点 | Gateway URL | Streaming | Usage 解析 | 状态 |
|---------|------------|-----------|-----------|------|
| Generate Content | `POST /gemini/v1beta/models/{model}:generateContent` | N/A | Expected | Expected |
| Stream Generate Content | `POST /gemini/v1beta/models/{model}:streamGenerateContent` | Expected | Expected | Expected |

**注意：** Gemini 路径结构特殊（`:generateContent` 后缀）、Usage 字段不同（`usageMetadata`）、Streaming 格式不同。复杂度明显高于 OpenAI Compatible Provider，因此降级到 P1。

### OpenRouter（`/openrouter/`）

| API 端点 | Gateway URL | Streaming | Usage 解析 | 状态 |
|---------|------------|-----------|-----------|------|
| Chat Completions | `POST /openrouter/v1/chat/completions` | Expected | Expected（OpenAI 格式） | Pending Validation |

### CC-Switch（`/ccswitch/`）

| API 端点 | Gateway URL | Streaming | Usage 解析 | 状态 |
|---------|------------|-----------|-----------|------|
| Chat Completions | `POST /ccswitch/v1/chat/completions` | Expected | Expected（OpenAI 格式） | Pending Validation |

---

## 客户端兼容性

### 可接入（Expected）

| 客户端 | 接入方式 | Base URL 示例 | 优先级 | 状态 |
|--------|---------|-------------|--------|------|
| **OpenAI SDK** | `base_url` 参数 | `http://127.0.0.1:8910/openai/v1` | **P0 (M1)** | Expected |
| **Cherry Studio** | API Address 设置 | `http://127.0.0.1:8910/openai` | **P0 (M2)** | Expected |
| **Anthropic SDK** | `base_url` 参数 | `http://127.0.0.1:8910/anthropic` | **P0 (M2)** | Expected |
| LangChain (OpenAI) | `openai_api_base` 参数 | `http://127.0.0.1:8910/openai/v1` | P1 | Expected |
| LangChain (Anthropic) | `anthropic_api_base` 参数 | `http://127.0.0.1:8910/anthropic` | P1 | Expected |
| LlamaIndex | `api_base` 参数 | `http://127.0.0.1:8910/openai/v1` | P1 | Expected |
| Continue | `apiBase` per model | `http://127.0.0.1:8910/openai/v1` | P1 | Expected |
| Open WebUI | `OPENAI_API_BASE` 环境变量 | `http://127.0.0.1:8910/openai/v1` | P1 | Expected |

### 不支持（Unsupported）

| 客户端 | 原因 | 替代方案 |
|--------|------|---------|
| **Claude Code** | 仅支持 `HTTP_PROXY` 环境变量，需要 CONNECT/HTTPS Tunnel | 无。当前架构不支持 CONNECT，无法统计 Claude Code Token。 |
| **Cursor (Copilot)** | 内置代理设置，可能不支持 Base URL 覆写 | 需验证 |

---

## 真实验证记录格式

以下为未来集成测试完成后的记录模板。当前全部为 `Pending Validation`。

### OpenAI — 待验证

```
SDK/Client:    OpenAI Python SDK
Version:       TBD
Base URL:      http://127.0.0.1:8910/openai/v1
Test:          Chat Completion (非流式)
Result:        Pending
Streaming:     Pending
Usage Parsing: Pending
Date:          TBD
```

### Anthropic — 待验证

```
SDK/Client:    Anthropic Python SDK
Version:       TBD
Base URL:      http://127.0.0.1:8910/anthropic
Test:          Messages API (非流式)
Result:        Pending
Streaming:     Pending
Usage Parsing: Pending
Date:          TBD
```

### Cherry Studio — 待验证

```
Client:        Cherry Studio
Version:       TBD
API Address:   http://127.0.0.1:8910/openai
Test:          Chat Completion (流式)
Result:        Pending
Streaming:     Pending
Usage Parsing: Pending
Date:          TBD
```

### Gemini — 待验证

```
SDK/Client:    Google GenAI SDK / 直接 API 调用
Version:       TBD
Base URL:      http://127.0.0.1:8910/gemini
Test:          generateContent (非流式)
Result:        Pending
Streaming:     Pending
Usage Parsing: Pending
Date:          TBD
```

---

## 功能支持矩阵

| 功能 | 当前状态 | 备注 |
|------|---------|------|
| Token 统计（非流式） | Expected | Parser 层已实现，待 Gateway 集成后验证 |
| Token 统计（SSE 流式） | Expected | SSE Handler 已实现，待 Gateway 集成后验证 |
| 费用计算 | Expected | CostCalculator 已实现 |
| 多 Provider 同时使用 | Expected | 通过不同前缀路由 |
| API Key 透传 | Expected | 默认模式 |
| API Key 管理模式 | Planned（阶段 2） | Windows Credential Manager + keyring |
| 无客户端代理支持的接入 | Expected | Gateway 模式核心价值 |
| Claude Code Token 统计 | **Unsupported** | 需要 CONNECT/TLS MITM，不在当前架构范围内 |

---

## 默认定价覆盖

| Provider | Model | Input \$/1M | Output \$/1M |
|----------|-------|------------|-------------|
| OpenAI | gpt-4o | \$2.50 | \$10.00 |
| OpenAI | gpt-4o-mini | \$0.15 | \$0.60 |
| OpenAI | o4-mini | \$1.10 | \$4.40 |
| OpenAI | o3 | \$10.00 | \$40.00 |
| Anthropic | claude-sonnet-4-20250514 | \$3.00 | \$15.00 |
| Anthropic | claude-opus-4-20250514 | \$15.00 | \$75.00 |
| Anthropic | claude-haiku-3.5 | \$0.80 | \$4.00 |
| DeepSeek | deepseek-chat | \$0.27 | \$1.10 |
| DeepSeek | deepseek-reasoner | \$0.55 | \$2.19 |
| Gemini | gemini-2.5-flash | \$0.15 | \$0.60 |
| Gemini | gemini-2.5-pro | \$1.25 | \$10.00 |

定价可通过 UI（Models 页面）用户自定义。

---

**本文档将在集成测试完成后更新为真实状态。**
