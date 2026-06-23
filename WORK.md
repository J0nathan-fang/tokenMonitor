# TokenMonitor 技术方案与数据链路

> AI Token 使用监控与费用分析工具 — Windows 桌面应用

---

## 1. 项目概述

TokenMonitor 是一个本地代理网关，运行在 `127.0.0.1:8910`，拦截电脑上所有 AI 客户端的 API 请求，实时提取 Token 用量、计算费用，并通过 PyQt6 桌面界面展示统计数据和趋势图表。

**核心价值：** 统一监控所有 AI 客户端的 Token 消耗，不依赖各客户端自身的统计功能。

---

## 2. 技术架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                   表示层 (Presentation)                       │
│  MainWindow │ FloatingWidget │ SystemTray │ 各Page页面        │
│                    (PyQt6)                                   │
├─────────────────────────────────────────────────────────────┤
│                   服务层 (Service)                            │
│  ProxyServiceThread(QThread) │ StatsService(QObject)         │
├─────────────────────────────────────────────────────────────┤
│                   业务层 (Business)                           │
│  StatisticsEngine │ CostCalculator │ ParserRegistry          │
├─────────────────────────────────────────────────────────────┤
│                   代理层 (Proxy)                              │
│  ProxyServer(aiohttp) │ ProxyHandler │ RequestForwarder      │
│  SSEHandler │ ProviderRouter │ EndpointResolver │ PathAdapter│
├─────────────────────────────────────────────────────────────┤
│                   解析层 (Parser)                             │
│  ProviderParser(ABC) → OpenAI │ Anthropic │ Gemini │ ...    │
├─────────────────────────────────────────────────────────────┤
│                   数据层 (Data)                               │
│  Repository → DatabaseManager(SQLite, WAL模式)               │
├─────────────────────────────────────────────────────────────┤
│                   基础设施 (Infrastructure)                   │
│  EventBus(Qt Signals) │ ConfigManager(YAML+DB) │ Logger      │
│  TokenCounter(tiktoken fallback) │ I18n(中/英)               │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 技术栈

| 层 | 技术 | 说明 |
|---|------|------|
| UI | PyQt6 + PyQt6-Charts + pyqtgraph | 桌面窗口、图表、系统托盘 |
| 异步 | asyncio + aiohttp + httpx | 代理服务器、HTTP转发 |
| 异步Qt桥接 | qasync | 将 asyncio 事件循环集成到 Qt |
| 数据验证 | Pydantic | 配置模型、数据校验 |
| 数据库 | SQLite (WAL模式) | 本地持久化、零配置 |
| Token计数 | tiktoken | API缺失usage时的回退计数 |
| 配置 | PyYAML | config.yaml 解析 |
| 导出 | openpyxl | Excel 导出 |
| 打包 | PyInstaller | 单文件 exe |

---

## 3. 双模代理架构 (Gateway + Proxy)

TokenMonitor 在单一端口 `8910` 上同时支持两种请求模式，通过 `ProxyServer._handle_all()` 自动分流：

### 3.1 请求分流逻辑

```
Request → 127.0.0.1:8910
  │
  ├─ URL路径以 /openai/、/anthropic/ 等前缀开头？
  │   └─ YES → Gateway 模式 → _handle_gateway()
  │
  └─ NO → URL包含已知AI API域名？
      ├─ YES → Proxy 模式 → handler.handle_request()
      └─ NO  → 通用转发 → _generic_forward()
```

### 3.2 Gateway 模式 (推荐)

客户端设置 `Base URL = http://127.0.0.1:8910`，发送相对路径请求。

**处理流程：**

```
Client: POST /openai/v1/chat/completions
  │
  ▼
ProviderRouter.resolve_and_normalize(path)
  ├─ resolve(): 前缀匹配 /openai → provider="openai"
  ├─ get_path_adapter("openai"): 获取 OpenAIPathAdapter
  └─ adapter.normalize(): /openai/v1/chat/completions → /v1/chat/completions
  │
  ▼
EndpointResolver
  ├─ resolve("openai"): 获取 EndpointConfig (base_url, auth header格式, actual_provider)
  ├─ build_target_url(): https://api.deepseek.com/v1/chat/completions
  └─ get_api_key_headers(): 透传模式的Auth header转译
  │
  ▼
ProxyHandler.handle_request(request, target_url=..., override_headers=...)
  → Forwarder → 解析 → 统计 → UI刷新
```

**Provider Identity 分离：**
- `client_type`：Router 检测的协议类型（如 `"openai"`）
- `actual_provider`：EndpointResolver 中的真实后端（如 `"deepseek"`）
- `pricing_version`：定价版本标识（如 `"2026-06-deepseek"`）

### 3.3 Proxy 模式 (兼容)

客户端设置 `HTTP_PROXY=http://127.0.0.1:8910`，发送完整真实 API URL。

```
Client: POST https://api.openai.com/v1/chat/completions
  │
  ▼
_is_ai_api_request(): URL匹配 AI_API_PATTERNS → true
  │
  ▼
ProxyHandler.handle_request(request)  # 无 target_url 覆盖
  → Forwarder → 解析 → 统计 → UI刷新
```

### 3.4 Gateway 路由配置

当前已注册的 Provider：

| client_type (路由前缀) | actual_provider | 目标 Base URL |
|------------------------|-----------------|---------------|
| `/openai/` | deepseek | `https://api.deepseek.com` |
| `/anthropic/` | anthropic | `https://api.anthropic.com` |

---

## 4. 完整数据链路

### 4.1 非流式请求 (以 OpenAI 为例)

```
1. AI Client 发送请求
   POST /openai/v1/chat/completions
   Body: {"model": "gpt-4o", "messages": [...], "stream": false}

2. ProxyServer._handle_all(request)
   └─ is_gateway_request("/openai/v1/chat/completions") → true
   └─ _handle_gateway(request)

3. _handle_gateway()
   ├─ ProviderRouter.resolve_and_normalize() → RouteResult(provider="openai", target_path="/v1/chat/completions")
   ├─ EndpointResolver.resolve("openai") → EndpointConfig(base_url="https://api.deepseek.com", ...)
   ├─ EndpointResolver.build_target_url() → "https://api.deepseek.com/v1/chat/completions"
   ├─ EndpointResolver.get_api_key_headers() → {"Authorization": "Bearer sk-xxx"} (透传转译)
   └─ handler.handle_request(request, target_url=..., override_headers=...)

4. ProxyHandler.handle_request()
   ├─ 读取 request_body = {"model": "gpt-4o", ...}
   ├─ _determine_usage_source(body) → "api" (非流式，API响应包含usage)
   ├─ _is_stream_request() → false
   └─ _handle_regular(request, url, headers, body)

5. ProxyHandler._handle_regular()
   ├─ RequestForwarder.forward(method, url, headers, body)
   │   └─ httpx.AsyncClient.request(url="https://api.deepseek.com/v1/chat/completions", ...)
   │   └─ 返回 (httpx.Response, latency_ms)
   │
   ├─ ParserRegistry.parse_response(response_body, url, headers, request_body)
   │   ├─ detect(url="https://api.deepseek.com/...", headers, body)
   │   │   └─ 遍历 parsers: CCSwitchParser → DeepSeekParser → ...
   │   │   └─ DeepSeekParser.can_parse() 匹配 "api.deepseek.com" → true
   │   ├─ DeepSeekParser.parse_response(response_body, request_body)
   │   │   └─ 继承自 OpenAIParser: response["usage"] → UsageData
   │   │   └─ UsageData(provider="deepseek", model="deepseek-chat", input_tokens=..., output_tokens=..., ...)
   │   └─ 注入 Provider Identity:
   │       usage.client_type = "openai"
   │       usage.actual_provider = "deepseek"
   │       usage.pricing_version = "2026-06-deepseek"
   │
   └─ StatisticsEngine.record(usage)
       ├─ CostCalculator.calculate(model, input, output, cache_read, cache_write)
       │   └─ 从 model_configs 表查询价格 (per 1M tokens)
       │   └─ 计算: input_cost + output_cost + cache_cost
       │   └─ 返回 CostResult(total_cost=...)
       │
       ├─ Repository.insert_request_log(log_entry)
       │   └─ INSERT INTO request_logs (18个字段含 provider identity + pricing)
       │
       ├─ Repository.upsert_daily_stats(stats_entry)
       │   └─ INSERT OR UPDATE daily_stats (按 date+provider+model 聚合)
       │
       └─ EventBus.new_request.emit(dict) + EventBus.stats_updated.emit()
           └─ UI各页面通过信号槽刷新显示

6. ProxyHandler 构建响应
   └─ 透传 API 响应 status + headers + body → 返回给客户端
```

### 4.2 流式请求 (SSE)

```
1. AI Client 发送流式请求
   POST /openai/v1/chat/completions
   Body: {"model": "gpt-4o", "messages": [...], "stream": true,
          "stream_options": {"include_usage": true}}

2-3. (Gateway路由解析同上)

4. ProxyHandler.handle_request()
   ├─ _determine_usage_source(body)
   │   └─ 检查 stream_options.include_usage:
   │       有 → "api" (usage在流中)
   │       无 → "token_counter_fallback" (需回退计数)
   ├─ _is_stream_request() → true
   └─ _handle_stream(request, url, headers, body)

5. ProxyHandler._handle_stream()
   ├─ RequestForwarder.forward_stream(method, url, headers, body)
   │   └─ httpx.AsyncClient.send(..., stream=True)
   │   └─ 返回 (AsyncIterator[bytes], connect_latency)
   │
   ├─ SSEHandler.process_stream(byte_iter, url, headers, body)
   │   └─ _SSERelayGenerator 异步生成器
   │       ├─ 逐块读取上游字节
   │       ├─ 缓冲拼接，按 \n\n 分割SSE事件
   │       ├─ 解析 "data: {json}" 行
   │       ├─ 跳过 "[DONE]" 标记
   │       ├─ registry.parse_stream_chunk(chunk, url, headers, body)
   │       │   └─ detect(url) → DeepSeekParser
   │       │   └─ OpenAIParser.parse_stream_chunk(chunk)
   │       │       └─ chunk["usage"] 存在 → 提取 UsageData
   │       └─ 累积保存最后的有效usage到 self._usage
   │
   ├─ 每块数据即时写入客户端 (实时中继)
   │
   └─ 流结束后提取 relay_iter.usage
       └─ StatisticsEngine.record(usage) (同上)
```

### 4.3 Usage Fallback 机制

```
请求分析:
  stream=true + stream_options.include_usage=true
    → usage_source = "api"
    → 从SSE最后chunk或JSON响应提取usage ✅

  stream=true 但 stream_options.include_usage 未设置
    → usage_source = "token_counter_fallback"
    → API流式响应不含usage字段
    → 需用 tiktoken 对响应文本计数 (当前阶段仅标记)

  stream=false (非流式)
    → usage_source = "api"
    → 从JSON响应 body["usage"] 提取 ✅
```

---

## 5. 核心模块设计

### 5.1 Parser 层 — Usage 解析器继承体系

```
ProviderParser (ABC)
  ├─ provider_name: str
  ├─ can_parse(url, headers, body) → bool
  ├─ parse_response(response_body, request_body, status_code) → UsageData | None
  ├─ parse_stream_chunk(chunk) → UsageData | None
  └─ extract_model(request_body, response_body) → str
  │
  ├── OpenAIParser (openai)
  │   解析: response["usage"] → {prompt_tokens, completion_tokens, total_tokens}
  │   URL匹配: api.openai.com, /v1/chat/completions, 及兼容API域名
  │   │
  │   ├── DeepSeekParser (deepseek)
  │   │   继承 OpenAI 解析格式，覆盖 can_parse 匹配 deepseek.com
  │   │
  │   ├── OpenRouterParser (openrouter)
  │   │   继承 OpenAI，覆盖 can_parse 匹配 openrouter.ai
  │   │   模型名从 response["model"] 获取 (路由后的实际模型)
  │   │
  │   └── CCSwitchParser (cc-switch)
  │       继承 OpenAI，支持 cc-switch 自定义 header 检测
  │       兼容 prompt_tokens / input_tokens 两种字段名
  │
  ├── AnthropicParser (anthropic)
  │   解析: response["usage"] → {input_tokens, output_tokens}
  │   缓存: cache_read_input_tokens, cache_creation_input_tokens
  │   SSE: message_stop / message_delta 事件提取 usage
  │
  └── GeminiParser (gemini)
      解析: response["usageMetadata"] → {promptTokenCount, candidatesTokenCount, totalTokenCount}
      模型从 response["modelVersion"] 获取

ParserRegistry:
  优先级: CCSwitch → DeepSeek → OpenRouter → Anthropic → Gemini → OpenAI(catch-all)
  每请求按顺序尝试 can_parse()，首个匹配即胜出
```

### 5.2 Statistics 层 — 统计引擎

```
StatisticsEngine.record(usage) → StatsSummary
  ├─ CostCalculator.calculate(model, ...) → CostResult
  │   ├─ 从 model_configs 表查价格 (exact → prefix → db lookup)
  │   ├─ 价格 per 1M tokens: input_price/1M × tokens
  │   └─ 缓存价格表到内存 (_price_cache)，或通过 refresh() 刷新
  │
  ├─ Repository.insert_request_log() → request_logs 表
  │   每条请求记录一行 (18个字段)
  │
  ├─ Repository.upsert_daily_stats() → daily_stats 表
  │   按 date + provider + model 唯一键聚合
  │   ON CONFLICT: 累加 tokens/requests/cost
  │
  └─ 返回 get_summary() → StatsSummary
      ├─ today_tokens / week_tokens / month_tokens
      ├─ today_cost / week_cost / month_cost
      ├─ active_models: 今日使用模型列表
      └─ top_models: 按总token排序的top5模型

StatsSummary (dataclass):
  - today_tokens / today_input_tokens / today_output_tokens
  - week_tokens / month_tokens
  - today_cost / week_cost / month_cost
  - today_requests
  - active_models: list[str]
  - top_models: list[{model, provider, client_type, total_tokens, cost}]
  - last_request_time
```

### 5.3 数据库 Schema

```
request_logs (每请求记录):
  id, timestamp, provider, client_type, actual_provider,
  model, endpoint, input_tokens, output_tokens, total_tokens,
  cache_read_tokens, cache_write_tokens, cost, currency,
  pricing_version, usage_source, latency_ms, status_code, created_at
  索引: timestamp, provider, model

daily_stats (日聚合表):
  id, date, provider, actual_provider, model,
  input_tokens, output_tokens, total_tokens,
  request_count, cost, currency, pricing_version
  UNIQUE(date, provider, model)

model_configs (模型定价配置):
  id, provider, model_name, display_name, api_url,
  input_price, output_price, cache_read_price, cache_write_price,
  currency, enabled, created_at, updated_at
  UNIQUE(provider, model_name)

budget_config (预算设置):
  id, budget_type(daily/weekly/monthly), amount, currency,
  notify_80, notify_90, notify_100, enabled

settings (键值配置):
  key (PRIMARY), value, updated_at
```

### 5.4 EventBus — 事件驱动通信

```
EventBus (Singleton, PyQt6 QObject):
  ├─ stats_updated: pyqtSignal()
  │   新的 Usage 数据已写入 DB，触发 UI 刷新
  │
  ├─ new_request: pyqtSignal(dict)
  │   每完成一次请求即发射，携带 usage 数据
  │
  ├─ budget_warning: pyqtSignal(int)  # 80/90/100
  │   预算阈值触发，TrayManager 弹出系统通知
  │
  ├─ proxy_status_changed: pyqtSignal(bool)
  │   代理服务器启停通知
  │
  └─ model_config_changed: pyqtSignal()
      模型配置变更 (增删改)，触发价格缓存刷新
```

### 5.5 UI 层 — 页面结构

```
MainWindow (QMainWindow)
  ├─ 侧边栏导航: 主页 | 历史记录 | 模型管理 | 预算管理 | 系统设置
  │
  ├─ DashboardPage: TokenCard×4, 模型饼图, 最近请求表
  ├─ HistoryPage: 日期选择器, 折线图/柱状图, CSV/Excel导出
  ├─ ModelsPage: 模型CRUD表格, 增删改对话框
  ├─ BudgetPage: 日/周/月预算设置, 进度条, 提醒阈值
  ├─ SettingsPage: 通用/代理/数据/显示设置
  │
  ├─ FloatingWidget: 桌面置顶半透明悬浮窗 (可拖拽)
  └─ TrayManager: 系统托盘图标 + 右键菜单
```

---

## 6. 关键设计决策

### 6.1 Provider Identity 分离

同一请求有三层身份标识：

| 字段 | 含义 | 示例 | 来源 |
|------|------|------|------|
| `provider` | Parser 识别的 Provider (用于统计聚合) | `"deepseek"` | ParserRegistry.detect() |
| `client_type` | Gateway 路由前缀对应的 SDK 协议类型 | `"openai"` | ProviderRouter.resolve() |
| `actual_provider` | 真实后端 API Provider | `"deepseek"` | EndpointResolver |

例如：用户用 OpenAI SDK 格式发请求，Gateway 路由 `/openai/...`，但实际后端是 DeepSeek API —— 费用按 DeepSeek 定价计算，但统计中保留"用 OpenAI 协议"的语义。

### 6.2 Router / PathAdapter / EndpointResolver 职责分离

遵循单一职责原则：
- **ProviderRouter**：仅负责 Provider 检测 (路径前缀 → provider名称)
- **PathAdapter**：每个 Provider 独立实现路径归一化 (剥离前缀、补全/v1、去重/v1)
- **EndpointResolver**：Provider → 目标 URL + Auth 头构建

新增 Provider 只需新增 PathAdapter 并在 `_DEFAULT_PROVIDERS` 注册，不修改 Router 代码。

### 6.3 单端口双模 (Gateway + Proxy)

不创建独立的 GatewayServer。两种模式共享同一个 aiohttp 实例和同一个 `8910` 端口，通过 `request.url.path` 形态自动区分：
- Gateway 请求路径是相对路径：`/openai/v1/chat/completions`
- Proxy 请求 URL 是完整地址：`https://api.openai.com/v1/chat/completions`

### 6.4 API Key 透传 (当前阶段)

客户端自行管理 API Key。TokenMonitor 剥离客户端 Header 的前缀 (如 `Bearer `)，然后以上游 API 期望的格式重新包装注入。不存储 Key。

未来阶段将支持从 Windows Credential Manager (keyring) 读取 Key 注入。

### 6.5 SSE 流式处理

`_SSERelayGenerator` 异步生成器模式：
1. 逐块从上游读取字节
2. 缓冲拼接，按 `\n\n` 分割 SSE 事件
3. 解析 `data:` 行 JSON，尝试提取 usage
4. 每块数据即时写入客户端 (不等待流结束)
5. 流结束后将累积的 usage 写入数据库

---

## 7. 启动与生命周期

```
main.py → Application
  │
  ├─ initialize()
  │   ├─ 1. ConfigManager.load() → config.yaml → AppConfig
  │   ├─ 2. setup_logging() (级别/文件/轮转)
  │   ├─ 3. DatabaseManager(db_path) → WAL模式, 建表, 迁移
  │   ├─ 4. 数据库 settings 覆盖 YAML 配置
  │   ├─ 5. Repository(db)
  │   ├─ 6. QApplication 创建
  │   ├─ 7. EventBus.get_instance() (Singleton)
  │   └─ 8. _seed_default_models() (首次运行预置模型价格)
  │
  └─ run()
      ├─ 创建 MainWindow(config, repository, event_bus)
      ├─ 启动 ProxyServiceThread(QThread)
      │   └─ 在新线程中运行 asyncio event loop
      │   └─ ProxyServer.start() → aiohttp 监听 127.0.0.1:8910
      ├─ QApplication.exec() (Qt 事件循环)
      │
      └─ shutdown()
          ├─ ProxyServiceThread.stop() → ProxyServer.stop()
          ├─ DatabaseManager.close()
          └─ EventBus.destroy_instance()
```

---

## 8. 支持的 Provider 与 Parser 兼容性

| Provider | Parser | 继承 | 非流式 | 流式 | 缓存Token | 格式 |
|----------|--------|------|--------|------|-----------|------|
| OpenAI | OpenAIParser | 基类 | ✅ | ✅ | cached_tokens | Chat Completions |
| DeepSeek | DeepSeekParser | OpenAI | ✅ | ✅ | - | OpenAI兼容 |
| OpenRouter | OpenRouterParser | OpenAI | ✅ | - | - | OpenAI兼容 |
| CC-Switch | CCSwitchParser | OpenAI | ✅ | - | - | OpenAI兼容 |
| Anthropic | AnthropicParser | 基类 | ✅ | ✅ | cache_read/write | Messages API |
| Gemini | GeminiParser | 基类 | ✅ | ✅ | - | GenerateContent |
| OpenAI兼容 | OpenAIParser | 基类 | ✅ | ✅ | - | vLLM/Ollama/Groq等 |

---

## 9. 支持的客户端配置方式

| 客户端 | Gateway 模式 | Proxy 模式 |
|--------|-------------|-----------|
| Cherry Studio | `API Address = http://127.0.0.1:8910/openai` | HTTP代理 `127.0.0.1:8910` |
| OpenAI SDK | `base_url = "http://127.0.0.1:8910/openai/v1"` | `HTTP_PROXY` 环境变量 |
| Anthropic SDK | `base_url = "http://127.0.0.1:8910/anthropic"` | `HTTP_PROXY` 环境变量 |
| Cursor/VSCode | - | 设置搜索 "proxy" |
| Continue | - | config.json `"proxy"` |
| Open WebUI | `OPENAI_API_BASE = http://127.0.0.1:8910/openai/v1` | - |
| Claude Code | - | ⚠️ 暂不支持 (需 CONNECT/HTTPS隧道) |

---

## 10. 目录结构

```
tokenMonitor/
├── src/
│   ├── main.py                 # 程序入口
│   ├── core/                   # 核心：配置、事件总线、启动引导
│   │   ├── app.py              # Application 生命周期管理
│   │   ├── config.py           # ConfigManager + AppConfig dataclass
│   │   └── event_bus.py        # EventBus Singleton (Qt Signals)
│   ├── proxy/                  # 代理服务器层
│   │   ├── server.py           # ProxyServer — 统一入口 (Gateway+Proxy双模)
│   │   ├── handler.py          # ProxyHandler — 请求编排 (转发→解析→统计)
│   │   ├── forwarder.py        # RequestForwarder — httpx HTTP转发
│   │   ├── sse_handler.py      # SSEHandler — SSE流解析+中继
│   │   ├── provider_router.py  # ProviderRouter — 路径前缀→Provider检测
│   │   ├── endpoint_resolver.py# EndpointResolver — Provider→目标URL+Auth
│   │   └── path_adapter.py     # PathAdapter — Provider特定路径归一化
│   ├── parser/                 # Usage 解析器
│   │   ├── base.py             # ProviderParser(ABC) + UsageData
│   │   ├── openai.py           # OpenAIParser (含兼容API)
│   │   ├── anthropic.py        # AnthropicParser
│   │   ├── gemini.py           # GeminiParser
│   │   ├── deepseek.py         # DeepSeekParser (继承OpenAI)
│   │   ├── openrouter.py       # OpenRouterParser (继承OpenAI)
│   │   ├── ccswitch.py         # CCSwitchParser (继承OpenAI)
│   │   └── registry.py         # ParserRegistry (自动检测)
│   ├── statistics/             # 统计引擎
│   │   ├── engine.py           # StatisticsEngine (记录+聚合+查询)
│   │   └── calculator.py       # CostCalculator (价格查询+费用计算)
│   ├── database/               # 数据层
│   │   ├── manager.py          # DatabaseManager (SQLite, WAL, 线程安全)
│   │   └── repository.py       # Repository (CRUD封装)
│   ├── services/               # 业务服务层
│   │   ├── proxy_service.py    # ProxyServiceThread (QThread封装)
│   │   └── stats_service.py    # StatsService (UI友好的统计接口)
│   ├── ui/                     # PyQt6 界面
│   │   ├── main_window.py      # MainWindow (侧边栏导航)
│   │   ├── floating.py         # FloatingWidget (桌面悬浮窗)
│   │   ├── tray.py             # TrayManager (系统托盘)
│   │   ├── theme.py            # ThemeManager (深色主题)
│   │   ├── dashboard/          # 仪表盘页面
│   │   ├── history/            # 历史记录页面
│   │   ├── models_page/        # 模型管理页面
│   │   ├── budget/             # 预算管理页面
│   │   ├── settings/           # 系统设置页面
│   │   └── widgets/            # 可复用组件 (TokenCard/Chart/Table)
│   └── utils/                  # 工具
│       ├── logger.py           # 日志配置 (文件轮转)
│       ├── token_counter.py    # tiktoken Token计数 (fallback)
│       └── i18n.py             # 国际化 (中/英文翻译表)
├── tests/                      # 测试
│   ├── integration/            # 集成测试
│   └── mock_provider.py        # Mock API Provider
├── tools/                      # 诊断工具
├── docs/                       # 架构/兼容性/验证报告
├── config.yaml                 # 应用配置
├── .env.example                # API Key 环境变量模板
├── requirements.txt            # Python 依赖
└── token_monitor.spec          # PyInstaller 打包配置
```

---

## 11. 未来规划

| 版本 | 目标 | 内容 |
|------|------|------|
| V1 (当前) | Gateway Mode | 双模代理、Provider路由、透传Auth、Token统计 |
| V2 | Default Provider | 无前缀请求自动路由到默认Provider |
| V3 | Forward Proxy | 完善非AI请求的透明转发 |
| V4 | TLS MITM Research | 评估HTTPS代理的技术可行性 (研究阶段) |

---

*最后更新: 2026-06-20*
