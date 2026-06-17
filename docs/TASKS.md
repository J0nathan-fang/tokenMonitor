# Tasks — TokenMonitor

> Updated: 2026-06-17 (v5 — M1 Prerequisite Adjustments)
> M1 成功标准 = OpenAI Gateway Verified，不是代码完成
> 新增：PathAdapter 层、推荐 base_url 标准化、Streaming Usage Fallback

---

## P0: SDK Path Discovery（Pre-Implementation）

**目标：** 在编写任何 Gateway 代码之前，通过诊断服务器捕获客户端实际发送的 HTTP 请求特征。

**方法：** 启动最小 HTTP Server → 配置客户端 → 发送请求 → 记录完整请求特征（含 body_shape）。

**原则：**
- ❌ 不基于文档猜测
- ❌ 不基于源码推断
- ✅ 必须真实验证
- ⚠️ **不记录完整 Prompt 内容，只记录结构（body_shape）**

**顺序：** OpenAI SDK → Cherry Studio → Anthropic SDK（Cherry Studio 优先，可能可复用 OpenAI 验证结果）

- [ ] P0.1 **OpenAI SDK Path Discovery** — 捕获 base_url 变体（`.../openai/v1`、`.../openai`），非流式 + 流式
- [x] P0.2 **Cherry Studio Path Discovery** — ✅ 2026-06-17 验证通过，路径行为与 OpenAI SDK 一致
- [ ] P0.3 **Anthropic SDK Path Discovery** — 捕获 base_url（`.../anthropic`），非流式 + 流式
- [ ] P0.4 填写 `docs/SDK_PATH_DISCOVERY.md` 并汇总结论
- [ ] P0.5 根据实际路径确定 ProviderRouter 匹配模式

**输出物：** `docs/SDK_PATH_DISCOVERY.md`（含真实 method、path、headers、body_shape）

**完成标准：** 所有客户端实际请求特征已记录，Router 匹配模式已确定。

---

## Milestone 1: OpenAI Gateway E2E

**目标：** OpenAI SDK → Gateway → OpenAI API → Usage Parse → Database → Dashboard Refresh，全部验证通过。

**规则：在 M1 完成前，不开发任何其他 Provider。**

### 1.1 基础组件

- [ ] 1.1.0 创建 `PathAdapter` 层：
  - `PathAdapter` 抽象基类 — `normalize(provider, path) -> str`
  - `OpenAIPathAdapter` — 处理 `/v1` 缺失（`/openai/chat/completions` → `/v1/chat/completions`）
  - `AnthropicPathAdapter` — 处理 double `/v1`（`/anthropic/v1/v1/messages` → `/v1/messages`）
  - **禁止在 Router 中使用 `replace()` 字符串替换**
- [ ] 1.1.1 创建 `ProviderRouter` — 仅负责 Provider 检测（`/openai` → `"openai"`，`/anthropic` → `"anthropic"`），路径归一化委托给 PathAdapter
- [ ] 1.1.2 创建 `EndpointResolver` — Provider → 目标 URL 映射（OpenAI 仅 `https://api.openai.com`）
- [ ] 1.1.3 修改 `ProxyHandler.handle_request()` — 增加 `target_url` 和 `override_headers` 可选参数
- [ ] 1.1.4 修改 `ProxyServer._handle_all()` — 集成 Gateway 分流逻辑
- [ ] 1.1.5 更新 `AppConfig` + `config.yaml` — 增加 `gateway` 配置段
- [ ] 1.1.6 更新 `ProxyService` + `Application` bootstrap 初始化
- [ ] 1.1.7 **Streaming Usage Fallback** — 当 stream=true 且无 `stream_options.include_usage` 时：记录 `Usage unavailable in stream response` 警告，自动启用 `TokenCounter` fallback

### 1.2 集成测试（必须先通过）

- [ ] 1.2.1 **OpenAI SDK 非流式** — Chat Completion → Gateway → OpenAI API → Usage 解析正确
- [ ] 1.2.2 **OpenAI SDK 流式** — SSE Chat Completion → Gateway → OpenAI API → Usage 解析正确
- [ ] 1.2.3 **Usage Tracking** — 验证 `request_logs` 表中字段正确（provider=openai, model, tokens, cost, latency）
- [ ] 1.2.4 **Dashboard 刷新** — 请求完成后 Dashboard 实时更新

### 1.3 Mock Provider

- [ ] 1.3.1 创建 `tests/mock_provider.py` — Mock OpenAI Compatible Endpoint
  - 支持 `POST /chat/completions`（非流式 + 流式）
  - 返回固定 Usage：`prompt_tokens=100, completion_tokens=50, total_tokens=150`
  - 流式返回 SSE 格式（`data:` 行，末尾含 `usage` 的 chunk）

### 1.4 集成测试 Harness

- [ ] 1.4.1 创建 `tests/integration/` 目录
- [ ] 1.4.2 `test_openai_gateway.py` — 非流式 E2E（优先使用 Mock，最终验证用真实 API）
- [ ] 1.4.3 `test_streaming.py` — 流式 E2E（Mock + 真实）
- [ ] 1.4.4 `test_usage_tracking.py` — Usage 统计准确性

### 1.5 集成测试（必须先通过）

- [ ] 1.5.1 **Mock → Gateway → Parser → Statistics → DB → Dashboard** — 完整链路闭环验证
- [ ] 1.5.2 **OpenAI SDK 非流式** — 真实 API → Usage 解析正确
- [ ] 1.5.3 **OpenAI SDK 流式** — 真实 API → Usage 解析正确
- [ ] 1.5.4 **Cost Calculation 验证** — 验证 `CostCalculator` 计算结果与官方定价一致

### 1.6 M1 交付物

- [ ] 1.6.1 `docs/SDK_PATH_DISCOVERY.md` — 含真实请求特征数据
- [ ] 1.6.2 OpenAI E2E 测试结果（Mock + 真实 API）
- [ ] 1.6.3 Usage Tracking Report — `request_logs` 记录验证
- [ ] 1.6.4 **Cost Verification Report** — 包含使用价格配置、计算过程、最终费用，验证与官方价格一致
- [ ] 1.6.5 Database Record Screenshot（`request_logs` + `daily_stats`）
- [ ] 1.6.6 Dashboard Screenshot
- [ ] 1.6.7 Known Issues List

**完成标准：M1 = OpenAI Gateway Verified。OpenAI SDK 可通过 Gateway 完成 请求 → 转发 → 解析 → 费用计算 → 存储 → 展示 全链路。**

---

## Milestone 2: Cherry Studio + Anthropic Gateway E2E

**前置条件：M1 完成。**

### 2.1 Anthropic Router 适配

- [ ] 2.1.1 基于 P0 发现结果，实现 Anthropic 路由匹配（宽松策略：匹配 provider 前缀 + endpoint 模式，不依赖精确路径）
- [ ] 2.1.2 注册 Anthropic 端点（`https://api.anthropic.com`）

### 2.2 集成测试

- [ ] 2.2.1 **Anthropic SDK 非流式** — Messages → Gateway → Anthropic API → Usage 含 cache 统计
- [ ] 2.2.2 **Anthropic SDK 流式** — SSE Messages → Gateway → Usage 从 `message_stop` 事件提取
- [x] 2.2.3 **Cherry Studio（OpenAI Compatible）** — ✅ 2026-06-17 Gateway E2E 验证通过，6 请求 4,966 tokens $0.002296
- [ ] 2.2.4 **Cherry Studio（Anthropic）** — API Address 接入 → Token 统计

---

## Milestone 3: 扩展 Provider

**前置条件：M2 完成。**

### P1 — Gemini（复杂度较高，降级到 P1）

- [ ] 3.1 Gemini Router — 路径结构特殊（`/v1beta/models/{model}:generateContent`）
- [ ] 3.2 Gemini 集成测试 — 非流式 + 流式
- [ ] 3.3 Usage 格式差异适配（`usageMetadata.promptTokenCount`）

### P1 — 其他 Provider

- [ ] 3.4 DeepSeek — `/deepseek/` 前缀
- [ ] 3.5 OpenRouter — `/openrouter/` 前缀
- [ ] 3.6 CC-Switch — `/ccswitch/` 前缀（目标 URL 可配置）

---

## Milestone 4: API Key 管理模式

**前置条件：M1 完成。**

- [ ] 4.1 集成 `keyring` 库 — Windows Credential Manager 安全存储
- [ ] 4.2 `EndpointResolver.get_api_key()` 管理模式 — 无客户端 Header 时注入 Key
- [ ] 4.3 Settings 页面 Key 管理 UI（脱敏显示）
- [ ] 4.4 集成测试 — 客户端无 Auth Header → 请求成功

---

## Milestone 5: 文档与扩展

- [ ] 5.1 `docs/GATEWAY_MODE.md` — 用户使用指南
- [ ] 5.2 更新 `docs/ARCHITECTURE.md` — Gateway 统一架构
- [ ] 5.3 更新 `README.md` — Gateway 模式说明
- [ ] 5.4 Provider 健康检查
- [ ] 5.5 自定义 Provider 注册

---

## 状态定义（文档中统一使用）

| 状态 | 含义 |
|------|------|
| **Expected** | 设计支持，尚未测试 |
| **Testing** | 已实现，正在验证 |
| **Verified** | 真实环境验证通过（需附日期、版本、测试结果） |

> **不得提前标记 Verified。**

---

## 已完成（架构审查）

- [x] 架构分析报告 — `docs/GATEWAY_ARCHITECTURE_ANALYSIS.md`（v2）
- [x] Provider 兼容性矩阵 — `docs/PROVIDER_COMPATIBILITY.md`（v2）
- [x] SDK 兼容性矩阵 — `docs/SDK_COMPATIBILITY.md`
- [x] SDK Path Discovery 模板 — `docs/SDK_PATH_DISCOVERY.md`
- [x] 架构决策确认：
  - [x] 扩展 ProxyServer（不创建独立 GatewayServer）
  - [x] API Key → Windows Credential Manager（keyring）
  - [x] Claude Code → Unsupported
  - [x] M1 仅 OpenAI（暂停其他 Provider）
  - [x] Gemini → P1

## 已完成（M1 — OpenAI Gateway E2E）

- [x] PathAdapter 层（OpenAI/Anthropic 独立实现）
- [x] ProviderRouter + EndpointResolver
- [x] ProxyServer Gateway 分流逻辑
- [x] ProxyHandler `target_url` / `override_headers` 参数
- [x] AppConfig + config.yaml gateway 配置段
- [x] ProxyServiceThread 集成到 Application bootstrap
- [x] Streaming Usage Fallback 机制
- [x] 92/92 Tests Passed

## 已完成（M2.1 — Cherry Studio Discovery）

- [x] `tools/cherry_studio_probe.py` — 请求特征捕获工具
- [x] Phase 1 (Probe Direct) — 捕获 4 条 Cherry Studio 1.8.0 真实请求
- [x] Phase 2 (Gateway E2E) — 6 条请求，4,966 tokens，验证通过
- [x] `docs/CHERRY_STUDIO_DISCOVERY_REPORT.md` — 完整报告
- [x] `docs/CLIENT_COMPATIBILITY.md` — 客户端兼容性矩阵
- [x] Provider Identity 分离验证：`client_type=openai` + `actual_provider=deepseek`
- [x] 结论：Cherry Studio 无需特判逻辑，现有 Gateway 直接兼容

---

## 历史（改造前）

- [x] SQLite Schema + 6 Parser + Statistics Engine + Cost Calculator
- [x] Dashboard / History / Models / Budget / Settings 全部 UI
- [x] 系统托盘 + 悬浮窗 + SSE 流式支持
- [x] 单元测试 + PyInstaller 打包
