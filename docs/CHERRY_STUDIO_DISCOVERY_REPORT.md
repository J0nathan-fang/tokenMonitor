# Cherry Studio Discovery Report

> **M2.1** — Cherry Studio Compatibility Validation
> **Date**: 2026-06-17
> **Status**: ✅ VERIFIED — Phase 1 (Probe Direct) + Phase 2 (Gateway E2E) 全部通过

---

## 测试环境

| 项目 | 值 |
|------|-----|
| Cherry Studio 版本 | 1.8.0 |
| 底层 Electron | 40.8.0 |
| 底层 Chrome | 144.0.7559.236 |
| OS | Windows 10.0 |
| 探测工具 | `tools/cherry_studio_probe.py` (端口 8911) |
| 目标 API | DeepSeek (`https://api.deepseek.com`) |
| 探测模式 | Direct（跳过 Gateway，Probe 自行路径归一化） |

---

## Cherry Studio 配置（Phase 1 使用）

| 字段 | 值 |
|------|-----|
| Provider Type | OpenAI Compatible |
| Base URL | `http://127.0.0.1:8911/openai/v1` |
| API Key | `sk-test`（Probe 自动注入真实 DEEPSEEK_API_KEY） |
| Model | `deepseek-v4-flash` |

---

## 捕获的请求特征

### 请求 #1 — 非流式

```
方法:   POST
路径:   /openai/v1/chat/completions
Query:  (空)
Headers:
    Authorization: Bearer sk-t***test
    Content-Type:  application/json
    x-title:       Cherry Studio                          ← Cherry Studio 特有
    User-Agent:    ...CherryStudio/1.8.0...Electron/40.8.0...
    http-referer:  https://cherry-ai.com                  ← Cherry Studio 特有
    Accept:        */*
Body Shape:
    model:          "deepseek-v4-flash"
    messages_count: 1
    first_message_role: "user"
    stream:         (不存在 — 非流式)
```

### 请求 #2 — 流式

```
方法:   POST
路径:   /openai/v1/chat/completions
Query:  (空)
Headers: 同 #1
Body Shape:
    model:          "deepseek-v4-flash"
    messages_count: 4
    stream:         true
    stream_options: {"include_usage": true}
```

### 请求 #3 — 非流式

```
同 #1，messages_count=1
```

### 请求 #4 — 流式

```
同 #2，messages_count=5（探测中断，未记录响应）
```

---

## 关键发现

### 1. 路径行为：与 OpenAI SDK 完全一致

Cherry Studio 1.8.0 使用 OpenAI Compatible Provider 时，路径行为与 OpenAI Python SDK 2.30.0 相同：

| Base URL | 实际请求路径 |
|----------|------------|
| `http://127.0.0.1:8911/openai/v1` | `/openai/v1/chat/completions` |

**结论：** Cherry Studio 直接在 Base URL 后拼接 `/chat/completions`，不修改 /v1 前缀。现有 `OpenAIPathAdapter` 可直接处理此路径。

### 2. 可识别的 Cherry Studio Headers

| Header | 值 | 用途 |
|--------|---|------|
| `x-title` | `Cherry Studio` | **唯一标识** — 可用于客户端类型检测 |
| `User-Agent` | `...CherryStudio/1.8.0...` | 版本标识 |
| `http-referer` | `https://cherry-ai.com` | Cherry Studio 特有 |

### 3. Auth 格式

Cherry Studio 使用 `Authorization: Bearer <key>`，与 OpenAI 格式一致。Gateway 当前 `EndpointResolver` 的透传模式可直接处理。

### 4. Stream 行为

Cherry Studio 在流式请求中**默认发送** `stream_options: {"include_usage": true}`（基于捕获的 #2 和 #4）。这意味着流式响应中会包含 usage 信息，**不需要 TokenCounter fallback**。

### 5. 与 TokenMonitor Gateway 的兼容性预测

| 组件 | 兼容性 | 说明 |
|------|--------|------|
| ProviderRouter | ✅ | `/openai/v1/chat/completions` → 前缀匹配 `/openai` |
| OpenAIPathAdapter | ✅ | 剥离 `/openai` → `/v1/chat/completions`（/v1 已存在，不补全） |
| EndpointResolver (openai → api.openai.com) | ⚠️ | 当前默认指向 OpenAI，需指向 DeepSeek |
| Auth 透传 | ✅ | `Authorization: Bearer` 格式一致 |
| 流式处理 | ✅ | `stream_options.include_usage` 已发送 |

---

## Phase 2 — Gateway E2E 验证 ✅

**日期**: 2026-06-17
**状态**: ✅ VERIFIED

### 测试配置

| 字段 | 值 |
|------|-----|
| Cherry Studio 版本 | 1.8.0 |
| Provider Type | OpenAI Compatible |
| Base URL | `http://127.0.0.1:8910/openai/v1` |
| API Key | DeepSeek API Key (`sk-...`) |
| Model | `deepseek-v4-flash` |
| Gateway 端口 | 8910 |
| Router 匹配 | `/openai` → client_type=openai |
| EndpointResolver | openai → `https://api.deepseek.com` (actual_provider=deepseek) |
| 定价版本 | `2026-06-deepseek` |

### Gateway 请求链路

```
Cherry Studio → POST /openai/v1/chat/completions
  → ProviderRouter.resolve() → client_type="openai"
  → OpenAIPathAdapter.normalize() → "/v1/chat/completions"
  → EndpointResolver.build_target_url() → "https://api.deepseek.com/v1/chat/completions"
  → ProxyHandler.handle_request(target_url=..., client_type="openai", actual_provider="deepseek")
  → RequestForwarder → DeepSeek API
  → ParserRegistry (DeepSeekParser) → UsageData
  → StatisticsEngine → Repository → EventBus → UI
```

### E2E 验证结果

| # | Model | Input | Output | Total | Cost (USD) | Latency | Source |
|---|-------|-------|--------|-------|------------|---------|--------|
| 1 | deepseek-v4-flash | 1012 | 66 | 1078 | $0.000346 | 1367ms | api |
| 2 | deepseek-v4-flash | 187 | 254 | 441 | $0.000330 | — | api |
| 3 | deepseek-v4-flash | 925 | 80 | 1005 | $0.000338 | 1249ms | api |
| 4 | deepseek-v4-flash | 247 | 353 | 600 | $0.000455 | — | api |
| 5 | deepseek-v4-flash | 1045 | 53 | 1098 | $0.000340 | 1116ms | api |
| 6 | deepseek-v4-flash | 399 | 345 | 744 | $0.000487 | — | api |
| **Total** | | **3815** | **1151** | **4966** | **$0.002296** | | |

### 验证检查项

| 检查项 | 状态 | 详情 |
|--------|------|------|
| Gateway 接收 Cherry Studio 请求 | ✅ | `POST /openai/v1/chat/completions` |
| Router Provider 识别 | ✅ | `/openai` 前缀 → provider="openai" |
| PathAdapter 路径归一化 | ✅ | `/openai/v1/chat/completions` → `/v1/chat/completions` |
| EndpointResolver 目标 URL | ✅ | `https://api.deepseek.com/v1/chat/completions` |
| Auth 透传 | ✅ | `Authorization: Bearer <key>` 正确转发 |
| 响应返回 Cherry Studio | ✅ | 用户确认正常收到回复 |
| Usage 解析 | ✅ | `usage_source=api`，全部从 API 响应解析 |
| Provider Identity 分离 | ✅ | `client_type=openai` + `actual_provider=deepseek` |
| 费用计算 | ✅ | DeepSeek 定价正确应用 |
| 定价版本追踪 | ✅ | `pricing_version=2026-06-deepseek` |
| 数据库写入 | ✅ | `request_logs` + `daily_stats` 正确 |
| Dashboard 更新 | ✅ | 控制台显示 token 统计 |

### 关键结论

1. **Cherry Studio 1.8.0 路径行为与 OpenAI SDK 完全一致** — 不需要任何特殊处理
2. **现有 Gateway 架构无需修改** — Router、PathAdapter、EndpointResolver 可直接处理 Cherry Studio
3. **Provider Identity 分离正确** — Cherry Studio 作为 OpenAI Compatible 客户端（client_type=openai），真实后端为 DeepSeek（actual_provider=deepseek）
4. **不需要 Cherry Studio 特判逻辑** — `x-title: Cherry Studio` header 可用于可选的客户端识别，但非必需

---

## 数据文件

原始捕获数据: `docs/cherry_studio_discovery_data.json`（4 条请求记录）
