# Gateway Mode — Architecture Analysis Report (修订版 v2)

> **Date:** 2026-06-17
> **Status:** Analysis Phase — Awaiting approval before implementation
> **Audience:** Developer — read before implementing

---

## Table of Contents

1. [Current Architecture Analysis](#1-current-architecture-analysis)
2. [Gateway Mode Design](#2-gateway-mode-design)
3. [Class Design](#3-class-design)
4. [Data Flow Diagrams](#4-data-flow-diagrams)
5. [Module Impact Matrix](#5-module-impact-matrix)
6. [Risk Analysis](#6-risk-analysis)
7. [Implementation Plan](#7-implementation-plan)
8. [Future Roadmap (V2–V4)](#8-future-roadmap-v2v4)
9. [Appendix: Key Design Decisions](#appendix-key-design-decisions)

---

## 1. Current Architecture Analysis

### 1.1 Forwarder 如何确定上游地址？

**结论：Forwarder 不负责确定上游地址。** `RequestForwarder`（`src/proxy/forwarder.py`）是一个纯粹的透传层 —— 客户端发来什么 URL，它就往什么 URL 转发。

```
Client sends: POST https://api.openai.com/v1/chat/completions
                    ↓ (via HTTP_PROXY=127.0.0.1:7890)
aiohttp receives:  request.url = "https://api.openai.com/v1/chat/completions"
                    ↓
handler.handle_request(request)
                    ↓
forwarder.forward(url="https://api.openai.com/v1/chat/completions", ...)
                    ↓
httpx.AsyncClient.request(url="https://api.openai.com/v1/chat/completions", ...)
```

整个链路中 **没有任何 URL 转换**，客户端必须先知道真实 API 的完整地址。

### 1.2 当前是否支持 Base URL Gateway 模式？

**不支持。** 当前唯一工作模式是 HTTP 代理。缺失：

- ❌ URL 前缀路由（如 `/openai/v1/...`）
- ❌ Provider → 目标地址映射
- ❌ 路径重写
- ❌ API Key 注入
- ❌ Gateway 端口配置

当前模式要求客户端必须：
1. 设置 HTTP 代理为 `127.0.0.1:7890`
2. 发送请求到**完整真实 API URL**

这意味着无法对接仅支持 Base URL 覆写的客户端（Cherry Studio 的 API 地址、OpenAI SDK 的 `base_url`、部分移动端 App）。

### 1.3 当前请求链路

```
AI Client (HTTP_PROXY=127.0.0.1:7890)
  │  POST https://api.openai.com/v1/chat/completions
  ▼
server.py:_handle_all()
  ├─ _is_ai_api_request() → 匹配 AI_API_PATTERNS
  ▼
handler.py:handle_request()
  ├─ 读取 body, 检测 stream
  ├─ forwarder.forward(url=str(request.url), ...) → httpx → Real API
  ├─ registry.parse_response(body, url, ...)
  │    └─ detect(url) → parser from URL host
  └─ engine.record(usage)
       ├─ calculator.calculate()
       ├─ repository.insert_request_log()
       └─ repository.upsert_daily_stats()
  ▼
event_bus.emit("stats_updated") → UI Refresh
```

### 1.4 架构优点（保留）

- 清晰的分层：Proxy → Parser → Statistics → Database → UI
- Parser 自动检测机制（从转发后的 URL 识别 Provider）
- SSE 缓冲解析，流式中转稳定
- 事件驱动 UI 更新
- Parser 继承体系（OpenAI 基类 → DeepSeek/OpenRouter/CCSwitch）

### 1.5 Gateway 模式缺口

- 无 URL → Provider 映射
- 客户端必须知道真实 API 地址
- 无法对接仅支持 Base URL 的客户端

---

## 2. Gateway Mode Design

### 2.1 核心思路：扩展 ProxyServer，而非新建 Server

**关键决策：在现有 `ProxyServer` 基础上扩展 Gateway 能力，不创建独立的 GatewayServer。**

理由：
- 避免生命周期管理重复
- 避免配置管理重复
- 避免日志系统重复
- 避免异常处理重复
- 单一 aiohttp 实例即可处理两种模式

架构：

```
Request arrives at 127.0.0.1:8910
        │
        ▼
  ProxyServer._handle_all(request)
        │
        ├── URL 以 /openai/、/anthropic/ 等前缀开头？
        │     ├── YES → Gateway 模式
        │     │   ├── ProviderRouter.resolve(path) → (provider, target_path)
        │     │   ├── EndpointResolver.build_target_url(provider, target_path)
        │     │   ├── EndpointResolver.get_api_key(provider, client_header)
        │     │   └── handler.handle_request(request, target_url=...)
        │     │
        │     └── NO → URL 匹配 AI_API_PATTERNS？
        │            ├── YES → Proxy 模式（现有逻辑）
        │            │   └── handler.handle_request(request)
        │            │
        │            └── NO → 通用转发（或拒绝）
        │
        ▼
  Forwarder → Parser → Statistics → DB → UI
  （以下全部不变）
```

**端口策略：**

| 端口 | 用途 | 默认值 |
|------|------|--------|
| Gateway 端口 | 统一入口（Gateway + Proxy 双模） | `8910` |

Gateway 模式下，客户端以相对路径发送请求（`/openai/v1/chat/completions`）。Proxy 模式下，客户端通过 HTTP 代理发送完整 URL。同一个 aiohttp 实例可以同时处理两种请求格式，因为 aiohttp 收到的 `request.url` 形态不同：

- Gateway 请求：`request.url.path = "/openai/v1/chat/completions"`（相对路径）
- Proxy 请求：`request.url = "https://api.openai.com/v1/chat/completions"`（完整 URL）

### 2.2 URL 路由规则

| Gateway 前缀 | 剥离后路径示例 | 目标 Base URL | 最终转发 URL |
|-------------|--------------|---------------|-------------|
| `/openai/` | `/v1/chat/completions` | `https://api.openai.com` | `https://api.openai.com/v1/chat/completions` |
| `/anthropic/` | `/v1/messages` | `https://api.anthropic.com` | `https://api.anthropic.com/v1/messages` |
| `/deepseek/` | `/v1/chat/completions` | `https://api.deepseek.com` | `https://api.deepseek.com/v1/chat/completions` |
| `/gemini/` | `/v1beta/models/{model}:generateContent` | `https://generativelanguage.googleapis.com` | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` |
| `/openrouter/` | `/v1/chat/completions` | `https://openrouter.ai/api` | `https://openrouter.ai/api/v1/chat/completions` |
| `/ccswitch/` | `/v1/chat/completions` | 可配置（config.yaml） | 取决于用户配置 |

**核心规则：** `{provider_prefix}` 之后的所有路径原样拼接到目标 Base URL。

```
请求:   /{provider}/{rest_of_path}
目标:   {base_url}/{rest_of_path}
```

### 2.3 API Key 管理模式

#### 模式 A：客户端透传（默认）

```
Client 发送 Authorization Header → TokenMonitor 原样转发
```

- 零配置
- 客户端自行管理 Key
- TokenMonitor 仅做统计

#### 模式 B：TokenMonitor 管理 Key（阶段 2 实现）

```
Client 无需发送 Authorization → TokenMonitor 从安全存储注入 Key
```

**存储方案：Windows Credential Manager（通过 `keyring` 库）**

最终选择此方案的理由：
1. 应用当前为 Windows 桌面应用（PyQt6），Windows Credential Manager 是 OS 原生支持
2. OS 级别加密，密钥与当前用户账户绑定，其他用户无法读取
3. 无需管理主密钥（避免 Fernet 方案中 "谁保管加密密钥" 的问题）
4. `keyring` 库提供统一 API，未来迁移到 macOS/Linux 时可自动切换至 Keychain / Secret Service
5. 备份时 API Key 不会随 DB 或 config.yaml 文件泄露

**安全性分析：**

| 方案 | 加密层级 | 密钥管理 | 跨平台 | 备份安全性 |
|------|---------|---------|--------|-----------|
| SQLite 明文 | 无 | N/A | ✅ | ❌ DB 文件即泄露 |
| config.yaml 明文 | 无 | N/A | ✅ | ❌ 配置文件即泄露 |
| config.yaml + Fernet | AES-128 | 需用户管理主密钥 | ✅ | ⚠️ 主密钥泄露即全部泄露 |
| **Windows Credential Manager** | **OS 级别（AES-256）** | **OS 自动管理** | ⚠️ 仅 Windows（keyring 可切换后端） | **✅ Key 不与数据文件一起备份** |

**备份与迁移方案：**
- API Key 不存储在 DB 或 config.yaml 中，数据库备份不包含 Key
- 如需迁移 Key，通过 UI 手动导出/导入（加密的 JSON 文件，需用户设置导出密码）
- 未来可集成到 Windows 账户漫游（Credential Manager 本身支持域环境下的漫游）

**配置结构：**

```yaml
# config.yaml — gateway 段
gateway:
  port: 8910
  api_key_mode: passthrough  # "passthrough" | "managed"
  providers:
    openai:
      enabled: true
      base_url: https://api.openai.com
    anthropic:
      enabled: true
      base_url: https://api.anthropic.com
    deepseek:
      enabled: true
      base_url: https://api.deepseek.com
    gemini:
      enabled: true
      base_url: https://generativelanguage.googleapis.com
    openrouter:
      enabled: true
      base_url: https://openrouter.ai/api
    ccswitch:
      enabled: true
      base_url: ""  # 用户配置
```

### 2.4 兼容策略

| 模式 | 端口 | 客户端配置 | URL 格式 |
|------|------|-----------|---------|
| Gateway（新增） | `8910` | `Base URL = http://127.0.0.1:8910` | `/{provider}/v1/...` |
| Proxy（保留） | `8910`（同端口） | `HTTP_PROXY=http://127.0.0.1:8910` | 完整真实 URL |

两种模式**共享同一端口、同一 aiohttp 实例、同一后端链路**。服务器根据请求 URL 形态自动判断模式。

### 2.5 Claude Code 支持状态

**状态：Unsupported（当前架构不支持）**

理由：

当前架构：
- ❌ 不支持 CONNECT 方法
- ❌ 不支持 HTTPS Tunnel
- ❌ 不支持 TLS MITM

Claude Code 作为 CLI 工具，仅支持通过 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量配置代理。在标准 HTTP 代理模式下，HTTPS 请求需要通过 CONNECT 隧道。TokenMonitor 当前不实现 CONNECT，因此**无法截获 Claude Code 的 HTTPS 请求内容**，进而无法解析 Token Usage。

**可能的路径（不在当前版本规划内）：**

| 方案 | 可行性 | 风险 |
|------|--------|------|
| Claude Code 支持 `base_url` 配置 | 需等待 Anthropic 官方支持 | 无 |
| 实现 CONNECT + TLS MITM | 技术复杂度极高 | 证书信任链、性能开销 |
| Claude Code 使用 Gateway 模式的 wrapper 脚本 | 可通过自定义脚本拦截 | 非原生体验 |

**当前结论：Claude Code 的 Token 统计不在 V1 Gateway 版本的支持范围内，标记为 Future Investigation。**

---

## 3. Class Design

### 3.1 新增类

#### PathAdapter（Provider 特定路径归一化）

```python
# src/proxy/path_adapter.py（新增）

from abc import ABC, abstractmethod

class PathAdapter(ABC):
    """Provider 特定路径归一化。

    禁止在 Router 层使用 replace() 做字符串替换式路径修正。
    每个 Provider 独立实现自己的 PathAdapter。

    Router 负责：Provider Detection
    PathAdapter 负责：Provider Specific Path Normalization
    """

    @abstractmethod
    def normalize(self, path: str) -> str:
        """将来自 Gateway 的请求路径归一化为上游 API 路径。

        Args:
            path: Gateway 接收到的完整请求路径（含 provider 前缀）。

        Returns:
            归一化后的路径（不含 provider 前缀，可直接拼接 base_url）。
        """
        ...


class OpenAIPathAdapter(PathAdapter):
    """OpenAI 路径归一化。

    处理规则：
    1. 剥离 provider 前缀 /openai
    2. 检测 /v1 前缀：有则保留，无则补全
    - /openai/v1/chat/completions → /v1/chat/completions
    - /openai/chat/completions    → /v1/chat/completions  (补全 /v1)
    """

    PROVIDER_PREFIX = "/openai"

    def normalize(self, path: str) -> str:
        target = path
        if target.startswith(self.PROVIDER_PREFIX):
            target = target[len(self.PROVIDER_PREFIX):]
        # 确保以 / 开头
        if not target.startswith("/"):
            target = "/" + target
        # 补全 /v1
        if not target.startswith("/v1"):
            target = "/v1" + target
        return target


class AnthropicPathAdapter(PathAdapter):
    """Anthropic 路径归一化。

    处理规则：
    1. 剥离 provider 前缀 /anthropic
    2. 检测并去重 double /v1
    - /anthropic/v1/messages      → /v1/messages
    - /anthropic/v1/v1/messages   → /v1/messages   (去重)
    """

    PROVIDER_PREFIX = "/anthropic"

    def normalize(self, path: str) -> str:
        target = path
        if target.startswith(self.PROVIDER_PREFIX):
            target = target[len(self.PROVIDER_PREFIX):]
        if not target.startswith("/"):
            target = "/" + target
        # 去重 double /v1
        if target.startswith("/v1/v1"):
            target = target[3:]  # 去掉多余的 "/v1"
        return target


# Provider → PathAdapter 注册表
PATH_ADAPTERS: dict[str, PathAdapter] = {
    "openai": OpenAIPathAdapter(),
    "anthropic": AnthropicPathAdapter(),
    # 未来扩展
    # "gemini": GeminiPathAdapter(),
    # "deepseek": DeepSeekPathAdapter(),
    # "openrouter": OpenRouterPathAdapter(),
}


def get_path_adapter(provider: str) -> PathAdapter | None:
    """获取指定 Provider 的 PathAdapter。"""
    return PATH_ADAPTERS.get(provider)
```

#### ProviderRouter

```python
# src/proxy/provider_router.py（新增）

class RouteResult:
    """Gateway URL 前缀解析结果。"""
    provider: str          # "openai", "anthropic", ...
    target_path: str       # 去除 provider 前缀后的路径（未归一化）
    matched: bool          # 是否为有效的 Gateway 路由

class ProviderRouter:
    """URL 路径前缀 → Provider 映射。

    仅负责 Provider 检测，不负责路径修正。
    路径归一化由 PathAdapter 层独立处理。

    通过 P0 SDK Path Discovery 确定实际匹配模式后最终调整。
    """

    # Provider 路由定义（宽松前缀匹配，支持变体）
    _route_definitions: list[dict]
    # 每个定义包含：
    # {
    #     "provider": "openai",
    #     "prefixes": ["/openai"],       # 匹配所有以这些前缀开头的路径
    # }
    #
    # 默认注册（基于 P0 验证结果调整）：
    # [
    #     {"provider": "openai",     "prefixes": ["/openai"]},
    #     {"provider": "anthropic",  "prefixes": ["/anthropic"]},
    #     {"provider": "deepseek",   "prefixes": ["/deepseek"]},
    #     {"provider": "gemini",     "prefixes": ["/gemini"]},
    #     {"provider": "openrouter", "prefixes": ["/openrouter"]},
    #     {"provider": "cc-switch",  "prefixes": ["/ccswitch"]},
    # ]

    def resolve(self, path: str) -> RouteResult:
        """解析路径并识别 Provider（仅检测，不归一化）。

        路径归一化由 resolve_and_normalize() 委托给 PathAdapter。

        支持以下变体（以 OpenAI 为例）：
        - /openai          → provider="openai"
        - /openai/         → provider="openai"
        - /openai/v1       → provider="openai"
        - /openai/v1/      → provider="openai"
        - /openai/v1/chat/completions
                           → provider="openai"
        """

    def resolve_and_normalize(self, path: str) -> RouteResult | None:
        """解析 Provider 并委托 PathAdapter 归一化路径。

        流程：
        1. resolve(path) → 检测 Provider
        2. get_path_adapter(provider) → 获取对应的 PathAdapter
        3. adapter.normalize(path) → 归一化 target_path
        4. 返回 RouteResult（含归一化后的 target_path）
        """

    def is_gateway_request(self, path: str) -> bool: ...
```

### Router 路径变体兼容策略

**核心原则：Router 负责 Provider Detection，PathAdapter 负责 Path Normalization。**

不同客户端和 SDK 版本的 Base URL 拼接行为存在差异。Router 宽容匹配 Provider 前缀，PathAdapter 对每个 Provider 独立处理路径归一化：

| 客户端/ SDK | 可能的实际路径 | Router 结果 | PathAdapter 归一化 |
|------------|-------------|------------|-------------------|
| OpenAI SDK（`base_url=.../openai/v1`） | `/openai/v1/chat/completions` | provider=openai ✅ | OpenAIPathAdapter → `/v1/chat/completions` |
| OpenAI SDK（`base_url=.../openai`） | `/openai/chat/completions` | provider=openai ✅ | OpenAIPathAdapter → `/v1/chat/completions`（补全 /v1） |
| Anthropic SDK（`base_url=.../anthropic`） | `/anthropic/v1/messages` | provider=anthropic ✅ | AnthropicPathAdapter → `/v1/messages` |
| Anthropic SDK（`base_url=.../anthropic/v1`） | `/anthropic/v1/v1/messages` | provider=anthropic ✅ | AnthropicPathAdapter → `/v1/messages`（去重 /v1） |

**实现要点：**
1. Router 提取路径第一个路径段作为 provider 候选（`path.split("/")[1]`）
2. Router 在 `_route_definitions` 中查找匹配的 provider
3. **Router 调用 `get_path_adapter(provider).normalize(path)` 获取归一化路径**
4. EndpointResolver 的 `base_url + normalized_path` 拼接最终的完整 URL

### Anthropic 宽松匹配策略

**问题：** Anthropic SDK 不同版本的路径构造方式不同：
- 新版本 (0.109.2)：`/anthropic/v1/messages`（SDK 内置追加 `/v1/messages`）
- 用户误配置 `/anthropic/v1` ：`/anthropic/v1/v1/messages`（double /v1）
- 旧版本：`/anthropic/messages`（不含 `/v1`）

**策略：Provider 前缀匹配 + PathAdapter 归一化。**

```
不实现：
  ❌ if path == "/anthropic/v1/messages" → anthropic
  ❌ path.replace("/v1/v1", "/v1")  ← 禁止字符串替换

而实现：
  ✅ if path starts with "/anthropic" → provider=anthropic
     AnthropicPathAdapter.normalize(path) → /v1/messages
```

**PathAdapter 职责明确：**
- Router: 识别 Provider（`/anthropic` → `"anthropic"`）
- AnthropicPathAdapter: 归一化路径（剥离前缀 + 去重 /v1）
- EndpointResolver: 拼接目标 URL（`base_url + normalized_path`）

**为什么不在 Router 层做路径修正？**
- Router 的职责是识别 Provider，不是修正路径
- 路径修正逻辑是 Provider 特定的，放入 Adapter 确保隔离
- 新增 Provider 只需新增 Adapter，不修改 Router 代码
- 符合开闭原则 (OCP)

#### EndpointResolver

```python
# src/proxy/endpoint_resolver.py（新增）

class EndpointConfig:
    """单个 Provider 的端点配置。"""
    provider: str
    base_url: str                      # "https://api.openai.com"
    enabled: bool = True
    api_key_header: str = "Authorization"
    api_key_prefix: str = "Bearer "

class EndpointResolver:
    """Provider 名称 → 目标 Base URL + API Key 解析。

    接收 ProviderRouter 解析的 provider + PathAdapter 归一化的 path，
    拼接为完整的 upstream URL。

    从 config.yaml 加载 Provider 配置。
    API Key 通过 keyring 从 Windows Credential Manager 读取（管理模式）。
    """

    _providers: dict[str, EndpointConfig]

    def resolve(self, provider: str) -> EndpointConfig | None: ...
    def build_target_url(self, provider: str, normalized_path: str) -> str | None:
        """拼接目标 URL。

        Args:
            provider: Provider 名称（如 "openai"）。
            normalized_path: PathAdapter 归一化后的路径（如 /v1/chat/completions）。

        Returns:
            完整 upstream URL（如 https://api.openai.com/v1/chat/completions）。
        """
    def get_api_key(self, provider: str, client_header: str | None) -> str | None:
        """解析 API Key。

        透传模式：返回客户端 Header 中的 Key（去除前缀）。
        管理模式：从 Windows Credential Manager 读取 Key。
        如果管理模式且无存储 Key，返回 None（请求将无 Auth Header 转发）。
        """
    def register_provider(self, config: EndpointConfig) -> None: ...
    def remove_provider(self, provider: str) -> None: ...
```

### 3.2 修改的类

#### ProxyServer（`server.py`）— 核心变更

```python
class ProxyServer:
    """统一 HTTP 服务器 — 同时支持 Gateway 模式和 Proxy 模式。

    在同一端口上处理两种请求格式：
    - Gateway：URL 以 /openai/、/anthropic/ 等前缀开头
    - Proxy：URL 为完整真实 API 地址（通过 HTTP 代理发送）
    """

    host: str
    port: int  # 默认 8910
    router: ProviderRouter        # 新增
    resolver: EndpointResolver    # 新增
    handler: ProxyHandler

    async def _handle_all(self, request: web.Request) -> web.StreamResponse:
        """统一入口——根据 URL 形态自动分流。"""
        path = request.url.path

        # 1. 检测 Gateway 请求
        if self._router.is_gateway_request(path):
            return await self._handle_gateway(request)

        # 2. 检测 AI API 代理请求（现有逻辑）
        if self._is_ai_api_request(str(request.url), dict(request.headers)):
            return await self._handler.handle_request(request)

        # 3. 通用转发
        return await self._generic_forward(request)

    async def _handle_gateway(self, request: web.Request) -> web.StreamResponse:
        """Gateway 模式请求处理。"""
        # 1. 解析路由
        route = self._router.resolve(request.url.path)
        if not route.matched:
            return web.Response(status=404, text="Unknown provider")

        # 2. 构建目标 URL
        target_url = self._resolver.build_target_url(
            route.provider, route.target_path)
        if not target_url:
            return web.Response(status=502, text="Provider not configured")

        # 3. 解析 API Key
        client_auth = request.headers.get("Authorization", "")
        api_key = self._resolver.get_api_key(route.provider, client_auth)

        # 4. 注入 Key（管理模式）
        headers = dict(request.headers)
        if api_key and not client_auth:
            config = self._resolver.resolve(route.provider)
            headers[config.api_key_header] = f"{config.api_key_prefix}{api_key}"

        # 5. 委托给 Handler
        return await self._handler.handle_request(
            request, target_url=target_url, override_headers=headers)
```

#### ProxyHandler（`handler.py`）— 少量变更

```python
class ProxyHandler:
    async def handle_request(
        self,
        request: Request,
        target_url: str | None = None,       # 新增：Gateway 模式下的目标 URL
        override_headers: dict | None = None, # 新增：API Key 注入后的 Headers
    ) -> web.StreamResponse:
        url = target_url or str(request.url)
        headers = override_headers or dict(request.headers)
        # ... 后续逻辑不变 ...
```

### 3.3 不变的类

| 类 | 文件 | 不变原因 |
|---|---|---|
| `RequestForwarder` | `forwarder.py` | 仍然向给定 URL 转发——URL 怎么来的不重要 |
| `SSEHandler` | `sse_handler.py` | 解析响应字节流，与请求来源无关 |
| 全部 Parser（6 个） | `parser/*.py` | `can_parse()` 检查的是**转发后的目标 URL**（含真实 API 域名） |
| `ParserRegistry` | `registry.py` | 自动检测逻辑不变 |
| `StatisticsEngine` | `statistics/engine.py` | 接收 UsageData，来源无关 |
| `CostCalculator` | `statistics/calculator.py` | 同上 |
| `DatabaseManager` | `database/manager.py` | Schema 无需变更（API Key 不存 DB） |
| `Repository` | `database/repository.py` | CRUD 操作不变 |
| `EventBus` | `core/event_bus.py` | 信号不变 |
| 全部 UI（12 个文件） | `ui/*` | 展示统计数据，不感知请求来源 |
| `StatsService` | `services/stats_service.py` | 服务层不变 |

### 3.4 类关系图

```
┌──────────────────────────────────────────────────────────────────┐
│                     Unified Server Architecture                   │
│                                                                   │
│  ┌──────────────────┐     ┌──────────────────────┐                │
│  │  ProviderRouter  │     │  EndpointResolver    │                │
│  │  ─────────────── │     │  ─────────────────── │                │
│  │ + resolve(path)  │     │ + resolve(provider)  │                │
│  │ + is_gateway()   │     │ + build_target_url() │                │
│  └────────┬─────────┘     │ + get_api_key()      │                │
│           │               └──────────┬───────────┘                │
│           │                          │                            │
│           └──────────┬───────────────┘                            │
│                      │                                            │
│                      ▼                                            │
│           ┌──────────────────────────┐                            │
│           │     ProxyServer          │  ← 扩展现有类               │
│           │     ──────────────       │                            │
│           │     host: str            │                            │
│           │     port: int (8910)     │                            │
│           │     router: PR           │                            │
│           │     resolver: ER         │                            │
│           │     handler: PH ─────────┼──────┐                     │
│           │                          │      │                     │
│           │  _handle_all(request)    │      │                     │
│           │   ├─ is_gateway?         │      │                     │
│           │   │   → _handle_gateway  │      │                     │
│           │   ├─ is_ai_api?          │      │                     │
│           │   │   → _handle_proxy    │      │                     │
│           │   └─ else                │      │                     │
│           │       → _generic_forward │      │                     │
│           └──────────────────────────┘      │                     │
│                                              │                     │
│                           ┌──────────────────┘                     │
│                           ▼                                        │
│           ┌──────────────────────────┐                            │
│           │     ProxyHandler         │  ← 少量变更                 │
│           │     ──────────────       │                            │
│           │ + handle_request(        │                            │
│           │     request,             │                            │
│           │     target_url=None,     │  ← 新增参数                 │
│           │     override_headers=    │  ← 新增参数                 │
│           │       None)              │                            │
│           └──────────┬───────────────┘                            │
│                      │                                            │
│           ┌──────────┼──────────┐                                 │
│           ▼          ▼          ▼                                 │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐                         │
│   │Forwarder │ │SSEHandler│ │ParserReg │  全部不变                │
│   └──────────┘ └──────────┘ └────┬─────┘                         │
│                                  │                                │
│           ┌──────────────────────┼────────────                    │
│           │      Statistics / DB / UI   全部不变                  │
│           └──────────────────────────────────                    │
│                                                                   │
│  Legend:                                                          │
│  ─── 新增类                                                       │
│  ─── 扩展现有类                                                    │
│  ─── 全部不变                                                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow Diagrams

### 4.1 Gateway 模式 — 非流式请求（OpenAI）

```
Client                          ProxyServer (Unified)          Real API
──────                          ─────────────────────          ────────

Base URL = http://127.0.0.1:8910

POST /openai/v1/chat/completions
Headers: {Authorization: Bearer sk-xxx}
Body: {model: "gpt-4o", messages: [...]}
        │
        ▼
┌──────────────────────────────┐
│ ProxyServer._handle_all()    │
│                              │
│ path = "/openai/v1/chat/     │
│         completions"         │
│                              │
│ router.is_gateway_request()  │
│   → true                     │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ ProxyServer._handle_gateway()│
│                              │
│ ① router.resolve(path)      │
│   → provider="openai"       │
│   → target_path="/v1/chat/  │
│     completions"            │
│                              │
│ ② resolver.build_target_    │
│   url("openai", target_path)│
│   → "https://api.openai.com │
│     /v1/chat/completions"   │
│                              │
│ ③ resolver.get_api_key(     │
│   "openai",                 │
│   "Bearer sk-xxx")          │
│   透传模式 → "sk-xxx"       │
│   管理模式 → keyring 读取    │
│                              │
│ ④ handler.handle_request(   │
│   request,                  │
│   target_url=...,           │
│   override_headers=...)     │
└──────────┬───────────────────┘
           │
           │  ← 以下全部不变 →
           │
           ▼
┌──────────────────────────────┐
│ RequestForwarder.forward()   │  不变
│ url="https://api.openai.com  │
│ /v1/chat/completions"        │ ──────► api.openai.com
└──────────┬───────────────────┘     ◄── JSON
           ▼
┌──────────────────────────────┐
│ ParserRegistry               │  不变
│ detect(url) → OpenAIParser   │
│ → UsageData                  │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ StatisticsEngine.record()    │  不变
│ → CostCalculator             │
│ → Repository                 │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ EventBus → UI Refresh        │  不变
└──────────────────────────────┘
```

### 4.2 Gateway 模式 — 流式请求（Anthropic SSE）

```
POST /anthropic/v1/messages
Headers: {x-api-key: sk-ant-xxx, anthropic-version: 2023-06-01}
Body: {model: "claude-sonnet-4-20250514", messages: [...], stream: true}
        │
        ▼
router.resolve("/anthropic/v1/messages")
  → provider="anthropic", target_path="/v1/messages"
        │
        ▼
resolver.build_target_url("anthropic", "/v1/messages")
  → "https://api.anthropic.com/v1/messages"
        │
        ▼
handler.handle_request(request, target_url=..., override_headers=...)
  → _is_stream_request() = true
  → forwarder.forward_stream(target_url, headers, body)
        │                  ──────► api.anthropic.com
        │              ◄── SSE ──
        ▼
SSEHandler.process_stream(byte_iter, target_url, ...)
  → 实时中转字节给客户端
  → 缓冲解析 SSE data: 行
  → registry.parse_stream_chunk(chunk, target_url)
      detect("api.anthropic.com") → AnthropicParser
      → message_stop / message_delta → UsageData
  → relay_iter.usage → UsageData
        │
        ▼
[同：StatisticsEngine → DB → EventBus → UI]
```

### 4.3 统一架构（单端口双模式）

```
                ┌───────────────────────────────────────┐
                │            TokenMonitor                │
                │       ProxyServer (Port 8910)           │
                │                                        │
Gateway 请求     │  POST /openai/v1/chat/completions      │
(Base URL=      │    → router.is_gateway() → true        │
 127.0.0.1:8910)│    → _handle_gateway()                  │
                │                                        │
Proxy 请求       │  POST https://api.openai.com/...       │
(HTTP_PROXY=    │    → _is_ai_api_request() → true       │
 127.0.0.1:8910)│    → handler.handle_request()          │
                │                                        │
                │            ┌──────────────┐            │
                │            │ ProxyHandler │ 共享       │
                │            └──────┬───────┘            │
                │                   │                    │
                │     ┌─────────────┴──────────┐         │
                │     │ Forwarder / SSE / Parser│ 共享   │
                │     └─────────────┬──────────┘         │
                │                   │                    │
                │     ┌─────────────┴──────────┐         │
                │     │ Statistics / DB / UI   │ 共享   │
                │     └────────────────────────┘         │
                └───────────────────────────────────────┘
```

---

## 5. Module Impact Matrix

| 模块 | 文件 | 变更级别 | 说明 |
|------|------|---------|------|
| **PathAdapter** | `src/proxy/path_adapter.py` | **新增** | Provider 特定路径归一化（OpenAI补全/v1, Anthropic去重/v1） |
| **ProviderRouter** | `src/proxy/provider_router.py` | **新增** | Provider 检测（仅负责识别，路径归一化委托 PathAdapter） |
| **EndpointResolver** | `src/proxy/endpoint_resolver.py` | **新增** | Provider → 目标 URL + API Key（keyring） |
| ~~GatewayServer~~ | ~~已删除~~ | **不需要** | 合并到 ProxyServer |
| ProxyServer | `src/proxy/server.py` | **中量修改** | 新增 router/resolver 成员，新增 `_handle_gateway()`，修改 `_handle_all()` 分流逻辑 |
| ProxyHandler | `src/proxy/handler.py` | **少量修改** | 新增可选参数 `target_url` 和 `override_headers` |
| RequestForwarder | `src/proxy/forwarder.py` | **不变** | 已 URL 无关 |
| SSEHandler | `src/proxy/sse_handler.py` | **不变** | — |
| ParserRegistry | `src/parser/registry.py` | **不变** | 从转发后 URL 检测 |
| 全部 Parser (6) | `src/parser/*.py` | **不变** | — |
| StatisticsEngine | `src/statistics/engine.py` | **不变** | — |
| CostCalculator | `src/statistics/calculator.py` | **不变** | — |
| DatabaseManager | `src/database/manager.py` | **不变** | API Key 不存 DB |
| Repository | `src/database/repository.py` | **不变** | — |
| EventBus | `src/core/event_bus.py` | **不变** | — |
| ConfigManager | `src/core/config.py` | **少量修改** | AppConfig 增加 `gateway` 段 |
| config.yaml | `config.yaml` | **少量修改** | 增加 `gateway` 配置段 |
| ProxyService | `src/services/proxy_service.py` | **少量修改** | 初始化 router/resolver 并注入 ProxyServer |
| App bootstrap | `src/core/app.py` | **少量修改** | 初始化 router/resolver |
| 全部 UI (12) | `src/ui/**/*.py` | **不变** | — |
| Settings page | `src/ui/settings/page.py` | **少量修改**（阶段 2） | Gateway 端口设置、Key 管理 UI |

**统计：**
- **3 个新增文件**（约 320 行，含 PathAdapter）
- **6 个少量/中量修改文件**
- **0 个独立 Server 类**
- **28 个文件不变**

---

## 6. Risk Analysis

### 6.1 技术风险

| 风险 | 严重度 | 可能性 | 缓解措施 |
|------|--------|--------|---------|
| **路径前缀冲突** — Provider 前缀与真实 API 路径冲突 | 低 | 低 | OpenAI/Anthropic/DeepSeek 等 API 不使用 `/openai/` 作为路径前缀 |
| **Cherry Studio 路径拼接行为不一致** — 不同版本拼接方式不同 | 中 | 中 | ProviderRouter 使用**前缀匹配**（`/openai/`）而非精确匹配；必须实测 |
| **OpenAI SDK `base_url` 自动追加路径** — SDK 自动追加 `/chat/completions` | 中 | 中 | 文档明确推荐 `base_url` 值；实测验证实际请求 URL |
| **Anthropic SDK 路径拼接** — 与 OpenAI SDK 不同，可能不含 `/v1` | 中 | 中 | 同上，实测确认 |
| **SSE 流式中继挂起** — 目标 URL 错误导致流挂起 | 中 | 低 | 已有 300s 超时（forwarder） |
| **API Key 泄露在日志中** | 中 | 中 | 日志中屏蔽 Authorization / x-api-key 头 |
| **Gateway 无鉴权** — localhost 内任意进程可访问 | 中 | 低 | 绑定 `127.0.0.1` 仅本地；v1 可接受 |
| **aiohttp 单实例承载双模式** | 低 | 低 | aiohttp 异步 I/O，单实例可处理数千并发 |

### 6.2 安全风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| **Windows Credential Manager 被恶意进程读取** | 高 — Key 泄露 | 需与当前用户账户权限相同；任何以当前用户运行的进程均有此风险；这是 OS 级别限制 |
| **内存中 Key 被 dump** | 中 — 运行时泄露 | Python 进程内存可被调试器读取；v1 接受此风险 |
| **config.yaml 中的 base_url 被篡改** | 中 — 请求被重定向到恶意服务器 | v1 接受（本地文件权限）；未来可增加配置签名校验 |

### 6.3 Cherry Studio — 需特别验证

Cherry Studio 的 API 地址配置行为：

```
用户设置 API Address: http://127.0.0.1:8910/openai

Cherry Studio 内部构造（取决于版本）:
  POST http://127.0.0.1:8910/openai/v1/chat/completions
  POST http://127.0.0.1:8910/openai/chat/completions
```

**必须在真实 Cherry Studio 中验证。** ProviderRouter 使用前缀匹配来兼容两种行为。

### 6.4 OpenAI SDK — 需特别验证

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8910/openai/v1",
    api_key="sk-xxx",
)
# SDK 构造: POST http://127.0.0.1:8910/openai/v1/chat/completions
# 预期路径: /openai/v1/chat/completions
# router.resolve() → provider="openai", target_path="/v1/chat/completions" ✅
```

### 6.5 Anthropic SDK — 需特别验证

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://127.0.0.1:8910/anthropic",
    api_key="sk-ant-xxx",
)
# SDK 构造:
#   POST http://127.0.0.1:8910/anthropic/v1/messages   ← 可能
#   POST http://127.0.0.1:8910/anthropic/messages       ← 也可能
# 必须在真实 SDK 中验证
```

---

## 7. Implementation Plan

### 状态定义（全文档统一）

| 状态 | 含义 | 何时使用 |
|------|------|---------|
| **Expected** | 设计支持，尚未测试 | 架构分析阶段 |
| **Testing** | 已实现，正在验证 | 编码完成后 |
| **Verified** | 真实环境验证通过 | 集成测试完成并确认结果正确后 |

> **不得在未经验证的情况下提前标记 Verified。**

---

### 优先级定义

| 优先级 | 含义 | 包含 |
|--------|------|------|
| **P0** | Pre-Implementation，必须在编码前完成 | SDK Path Discovery |
| **M1** | Milestone 1，唯一的第一里程碑 | OpenAI Gateway E2E |
| **M2** | Milestone 2，M1 完成后启动 | Cherry Studio + Anthropic |
| **M3** | Milestone 3，扩展 Provider | Gemini (P1) + DeepSeek + OpenRouter + CC-Switch |
| **M4** | Milestone 4，API Key 管理模式 | keyring 集成 |
| **M5** | Milestone 5，文档与增强 | 使用指南、健康检查 |

---

### P0: SDK Path Discovery（Pre-Implementation）

**目标：** 通过诊断服务器捕获客户端真实请求路径，确定 Router 匹配模式。

**规则：** 禁止基于文档猜测或 SDK 源码推断。必须通过真实 HTTP 请求验证。

| 步骤 | 任务 | 输出 |
|------|------|------|
| P0.1 | 启动诊断 HTTP 服务器（打印 method、path、headers） | `tools/path_discovery_server.py` |
| P0.2 | 捕获 OpenAI SDK 请求（base_url 变体） | 实际路径记录 |
| P0.3 | 捕获 Anthropic SDK 请求 | 实际路径记录 |
| P0.4 | 捕获 Cherry Studio 请求（OpenAI Provider） | 实际路径记录 |
| P0.5 | 捕获 Cherry Studio 请求（Anthropic Provider） | 实际路径记录 |
| P0.6 | 填写 `docs/SDK_PATH_DISCOVERY.md`，汇总结论 | 确定 Router 匹配模式 |

**输出物：** `docs/SDK_PATH_DISCOVERY.md`（含真实数据）

**完成标准：** 所有客户端实际请求路径已记录，ProviderRouter 路径变体支持策略已确定。

---

### Milestone 1: OpenAI Gateway E2E（当前唯一开发目标）

**目标：** OpenAI SDK → Gateway → OpenAI API → Usage Parse → Database → Dashboard Refresh

**规则：在 M1 验证通过之前，暂停所有其他 Provider 的开发。**

| 步骤 | 任务 | 验证 |
|------|------|------|
| **1.1 基础组件** | | |
| 1.1.1 | 创建 `ProviderRouter` — 基于 P0 发现的路径变体 | 单元测试：所有变体解析正确 |
| 1.1.2 | 创建 `EndpointResolver` — 仅注册 OpenAI | 单元测试：目标 URL 构建正确 |
| 1.1.3 | 修改 `ProxyHandler` — 增加 `target_url` / `override_headers` | 现有代理模式不受影响 |
| 1.1.4 | 修改 `ProxyServer` — 集成 Gateway 分流逻辑 | 单端口响应 Gateway + Proxy 请求 |
| 1.1.5 | 更新 `AppConfig` + `config.yaml` | Gateway 配置段加载 |
| 1.1.6 | 更新 bootstrap（`ProxyService` + `Application`） | router/resolver 初始化注入 |
| **1.2 集成测试 Harness** | | |
| 1.2.1 | 创建 `tests/integration/` 目录 | |
| 1.2.2 | `tests/integration/test_openai_gateway.py` | 非流式 E2E 通过 |
| 1.2.3 | `tests/integration/test_streaming.py` | 流式 E2E 通过 |
| 1.2.4 | `tests/integration/test_usage_tracking.py` | Usage 统计准确性通过 |
| **1.3 Mock Provider** | | |
| 1.3.1 | 创建 `tests/mock_provider.py` | Mock OpenAI Compatible Endpoint，支持非流式 + 流式 |
| **1.4 集成测试 Harness** | | |
| 1.4.1 | `tests/integration/test_openai_gateway.py` | |
| 1.4.2 | `tests/integration/test_streaming.py` | |
| 1.4.3 | `tests/integration/test_usage_tracking.py` | |
| **1.5 E2E 验证** | | |
| 1.5.1 | Mock → Gateway → Parser → Statistics → DB → Dashboard 闭环 | 集成测试优先使用 Mock Provider |
| 1.5.2 | OpenAI SDK 非流式 → Usage 解析正确 | `request_logs` 中数据完整 |
| 1.5.3 | OpenAI SDK 流式 → Usage 解析正确 | `request_logs` 中数据完整 |
| 1.5.4 | **Cost Calculation 验证** | 验证 prompt/ completion tokens → input/output cost → total cost，与官方定价一致 |
| 1.5.5 | Dashboard 实时刷新 | Dashboard + 悬浮窗更新 |
| **1.6 交付物** | | |
| 1.6.1 | `docs/SDK_PATH_DISCOVERY.md`（含真实数据） | |
| 1.6.2 | OpenAI E2E 测试结果 | |
| 1.6.3 | Usage Tracking Report | |
| 1.6.4 | **Cost Verification Report** — 包含使用价格配置、计算过程、最终费用 | |
| 1.6.5 | Database Record Screenshot | |
| 1.6.6 | Dashboard Screenshot | |
| 1.6.7 | Known Issues List | |

**M1 完成标准：M1 = OpenAI Gateway Verified。OpenAI SDK 可通过 Gateway 完成 请求 → 转发 → 解析 → 费用计算 → 存储 → 展示 全链路。**

---

### Milestone 2: Cherry Studio + Anthropic（M1 完成后）

| 步骤 | 任务 |
|------|------|
| 2.1 | 基于 P0 发现结果，实现 Anthropic 宽松匹配路由 |
| 2.2 | 注册 Anthropic 端点（`https://api.anthropic.com`） |
| 2.3 | Anthropic SDK 非流式 + 流式集成测试 |
| 2.4 | Cherry Studio（OpenAI + Anthropic Provider）集成测试 |

### Milestone 3: 扩展 Provider（M2 完成后）

| 优先级 | Provider | 说明 |
|--------|----------|------|
| **P1** | Gemini | 复杂度较高（路径结构特殊、Usage 字段不同、Streaming 格式不同） |
| P1 | DeepSeek | OpenAI 兼容 |
| P1 | OpenRouter | OpenAI 兼容 |
| P1 | CC-Switch | 目标 URL 可配置 |

### Milestone 4: API Key 管理模式（M1 完成后可并行）

| 步骤 | 任务 |
|------|------|
| 4.1 | 集成 `keyring` 库 — Windows Credential Manager |
| 4.2 | `get_api_key()` 管理模式 — 无 Header 时注入 |
| 4.3 | Settings UI — Key 管理（脱敏显示） |
| 4.4 | 集成测试 — 客户端无 Auth Header → 请求成功 |

### Milestone 5: 文档与增强

| 步骤 | 任务 |
|------|------|
| 5.1 | `docs/GATEWAY_MODE.md` — 用户使用指南 |
| 5.2 | 更新 `docs/ARCHITECTURE.md` + `README.md` |
| 5.3 | Provider 健康检查 |
| 5.4 | 自定义 Provider 注册

---

## 8. Future Roadmap (V2–V4)

### V1 — Gateway Mode（当前版本）

**Milestone 1（当前开发重点）：** OpenAI Gateway E2E
- ProviderRouter + EndpointResolver
- OpenAI SDK / Cherry Studio 集成测试
- 流式 + 非流式 Usage 统计
- Dashboard 实时刷新

**Milestone 2-3（后续扩展）：**
- P0: Anthropic, Cherry Studio
- P1: Gemini（路径结构特殊，复杂度较高）
- P1: DeepSeek, OpenRouter, CC-Switch

核心能力：
- 基于 URL 前缀的 Provider 路由（支持路径变体）
- 透传模式（客户端自带 Key）
- 管理模式（TokenMonitor 管理 Key，通过 Windows Credential Manager 存储）
- Token 统计与费用计算
- Dashboard 可视化

### V2 — Default Provider Mapping

**目标：** 用户无需在 URL 中指定 Provider 前缀。

```
当前:  POST /openai/v1/chat/completions
V2:    POST /v1/chat/completions  → 自动映射到默认 Provider（如 openai）
```

实现：
- 通过 `config.yaml` 配置 `default_provider: openai`
- 无前缀的请求自动路由到默认 Provider
- 显式前缀（`/openai/` 等）仍然生效，覆盖默认值

### V3 — Forward Proxy（仅转发，不统计）

**目标：** 支持标准 HTTP 代理模式下非 AI 请求的透明转发。

当前状态：
- 非 AI API 请求（不匹配 `AI_API_PATTERNS`）→ `_generic_forward()` 直接转发
- 已具备基本 Proxy 能力，但 Token 统计仅限于 AI API

V3 增强：
- 完善非 AI 流量的转发体验
- 不解析 Usage（因为没有）

### V4 — TLS MITM Research（仅研究）

**目标：** 评估 HTTPS 代理模式下 TLS 解密的技术可行性和安全影响。

当前状态：
- 不支持 CONNECT 方法
- 不支持 HTTPS Tunnel
- 不支持 TLS MITM

研究方向：
- 动态证书签发
- 系统信任链管理
- 性能开销评估
- 安全风险分析（中间人攻击的法律和伦理边界）

**V4 不纳入任何版本的开发计划，仅作为技术研究方向。** TokenMonitor 的产品定位是 **Unified AI Gateway + Token Analytics Platform**，不是 System-wide HTTP Proxy。

---

## Appendix: Key Design Decisions

### A.1: 为什么扩展 ProxyServer 而不是新建 GatewayServer？

**决策：扩展 ProxyServer。**

理由：
- 双 Server = 双份生命周期管理、配置管理、日志、异常处理、启停逻辑 → 维护负担翻倍
- aiohttp 单实例可同时处理 Gateway（相对路径）和 Proxy（完整 URL）两种请求格式
- 通过 `request.url.path` 判断是否为 Gateway 请求，逻辑清晰无歧义
- 共享后端（Forwarder/Parser/Statistics/DB）天然一致
- 减少约 150 行重复代码

### A.2: ProviderRouter 和 EndpointResolver 为何分开？

**决策：两个独立类。**

理由：
- ProviderRouter：URL 解析关注点（路径 → Provider）
- EndpointResolver：配置关注点（Provider → 目标 URL + API Key）
- 不同的扩展维度（新路由模式 vs 新 Provider）
- 可独立测试

### A.3: API Key 存储 — 最终选择 Windows Credential Manager

**决策：Windows Credential Manager（通过 `keyring` 库）。**

安全性对比：

| 方案 | 加密 | 密钥管理 | 备份安全 | 复杂度 |
|------|------|---------|---------|--------|
| SQLite 明文 | ❌ | N/A | ❌ | 最低 |
| config.yaml 明文 | ❌ | N/A | ❌ | 最低 |
| config.yaml + Fernet | AES-128 | 需用户管理主密钥 | ⚠️ 主密钥泄露即全泄露 | 中 |
| **Windows Credential Manager** | **OS 级 AES-256** | **OS 自动** | **✅ Key 不随数据文件备份** | 低（`keyring` 库封装） |

### A.4: Claude Code 状态

**决策：Unsupported（当前版本不统计 Claude Code Token 用量）。**

当前架构不支持：
- CONNECT 方法
- HTTPS Tunnel
- TLS MITM

这些是实现透明 HTTPS 代理的必要条件，不在 V1 Gateway 的开发范围内。Claude Code 的 Token 统计列为 Future Investigation。

---

**修订记录：**
- 2026-06-17 v1：初版
- 2026-06-17 v2：合并 GatewayServer 至 ProxyServer；确定 API Key 存储方案；移除未验证的兼容性声明；重评 Claude Code 状态；新增 V2-V4 Roadmap；重排实施优先级
- 2026-06-17 v3：新增 P0 SDK Path Discovery；重构 M1 为 OpenAI E2E 唯一里程碑；ProviderRouter 支持路径变体；Anthropic 宽松匹配策略；Gemini 降级至 P1；新增集成测试 Harness；统一状态定义
- 2026-06-17 v4：P0 扩展为完整请求特征记录（含 body_shape，不含完整 Prompt）；新增 Mock Provider；新增 Cost Calculation Verification 交付物；P0 顺序调整为 OpenAI → Cherry Studio → Anthropic；M1 成功标准 = OpenAI Gateway Verified
- 2026-06-17 v5：P0 验证完成（OpenAI SDK 2.30.0 + Anthropic SDK 0.109.2）；新增 PathAdapter 层（OpenAI/Anthropic 独立实现，禁止 Router 内 replace() 字符串替换）；更新推荐 base_url 配置；新增 Streaming Usage Fallback 机制

---

## Appendix B: Files That Will Be Created

```
src/proxy/
├── path_adapter.py              # NEW (~120 lines) — Provider 特定路径归一化
├── provider_router.py           # NEW (~100 lines) — Provider 检测（仅负责识别）
└── endpoint_resolver.py         # NEW (~100 lines) — Provider → 目标 URL

tools/
└── path_discovery_server.py  # NEW — P0 诊断 HTTP 服务器

tests/
└── integration/
    ├── __init__.py
    ├── test_openai_gateway.py   # NEW — OpenAI E2E
    ├── test_streaming.py        # NEW — 流式 E2E
    └── test_usage_tracking.py   # NEW — Usage 统计验证

docs/
├── SDK_PATH_DISCOVERY.md        # NEW — P0 路径发现结果
├── SDK_COMPATIBILITY.md         # NEW — SDK 兼容性矩阵 ✅ 已创建
├── GATEWAY_MODE.md              # NEW — 用户使用指南 (M5)
└── PROVIDER_COMPATIBILITY.md    # ✅ 已创建
```

## Appendix C: Files That Will Be Modified

```
src/proxy/server.py           # 中量修改 — 集成 Gateway 分流逻辑
src/proxy/handler.py           # 少量修改 — +target_url / +override_headers
src/core/config.py             # 少量修改 — +gateway 配置段
src/core/app.py                # 少量修改 — 初始化 router/resolver
src/services/proxy_service.py  # 少量修改 — router/resolver 注入
config.yaml                    # 少量修改 — +gateway 段
docs/ARCHITECTURE.md           # 更新 (M5)
README.md                      # 更新 (M5)
```

---

**End of Analysis Report — Awaiting approval before implementation.**
