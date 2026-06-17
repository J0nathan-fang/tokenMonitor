# SDK / Client Compatibility

> **TokenMonitor — Unified AI Gateway + Token Analytics Platform**
> Last updated: 2026-06-17
> Status: **Pre-Implementation** — 所有测试状态均为 Expected，待集成测试后更新

---

## 状态定义

| 状态 | 含义 |
|------|------|
| **Expected** | 基于 SDK 文档和代码分析，预期可通过 Gateway 接入 |
| **Testing** | 正在执行集成测试 |
| **Verified** | 已完成真实验证，确认可用（需附日期、版本、测试结果） |

> **重要约束：** 只有在完成真实联调测试后，状态才能更新为 Verified。当前所有条目均为 Expected。

---

## 1. OpenAI Python SDK

### 配置方式

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8910/openai/v1",
    api_key="sk-xxx",  # 透传模式：必需；管理模式：可选
)
```

### Base URL 说明

**推荐配置：** 使用包含 `/v1` 的 base_url。

```
base_url = "http://127.0.0.1:8910/openai/v1"  ← 推荐
base_url = "http://127.0.0.1:8910/openai"      ← 不推荐（路径缺 /v1，需 Gateway 补全）
```

SDK 在 `base_url` 之后直接追加 `/chat/completions`：
```
base_url = "http://127.0.0.1:8910/openai/v1"
SDK 构造: POST http://127.0.0.1:8910/openai/v1/chat/completions
Gateway 解析: /openai/v1/chat/completions → provider=openai, normalized=/v1/chat/completions
目标 URL: https://api.openai.com/v1/chat/completions ✅
```

> **P0 实测确认：** OpenAI SDK 2.30.0 不自动补 `/v1`。若用户配置 `base_url=.../openai`（不含 `/v1`），Gateway 的 OpenAIPathAdapter 会自动补全。推荐用户使用含 `/v1` 的配置以避免额外处理。

### 兼容性矩阵

| 功能 | Gateway 支持 | 测试状态 | 备注 |
|------|-------------|---------|------|
| Chat Completions（非流式） | Expected | Expected | `response.usage` → OpenAIParser |
| Chat Completions（流式） | Expected | Expected | SSE → `usage` in final chunk |
| Responses API | Expected | Expected | 同上 |
| Function Calling | Expected | Expected | Request body 透传，不影响路由 |
| Vision（图片输入） | Expected | Expected | 同上 |
| Embeddings | Expected | Expected | 无 Token 统计（无 usage 字段） |

### 验证记录（待填写）

```
SDK:          openai (Python)
Version:      TBD
Base URL:     http://127.0.0.1:8910/openai/v1
Test 1:       Chat Completion (非流式) → Result: Pending
Test 2:       Chat Completion (流式)   → Result: Pending
Test 3:       Responses API             → Result: Pending
Usage Stats:  Pending
Date:         TBD
```

---

## 2. Anthropic Python SDK

### 配置方式

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://127.0.0.1:8910/anthropic",
    api_key="sk-ant-xxx",
)
```

### Base URL 说明

**推荐配置：**

```
base_url = "http://127.0.0.1:8910/anthropic"     ← 推荐（SDK 内置 /v1）
base_url = "http://127.0.0.1:8910/anthropic/v1"   ← 不推荐（造成 double /v1）
```

**P0 实测确认（Anthropic SDK 0.109.2）：**
- SDK 在 base_url 后**自动追加** `/v1/messages`
- 正确：`base_url=.../anthropic` → `/anthropic/v1/messages` ✅
- 错误：`base_url=.../anthropic/v1` → `/anthropic/v1/v1/messages` ⚠️（double /v1）
- Gateway 的 AnthropicPathAdapter 自动去重 double /v1

```
base_url = "http://127.0.0.1:8910/anthropic"
SDK 构造: POST http://127.0.0.1:8910/anthropic/v1/messages
Gateway 解析: /anthropic/v1/messages → provider=anthropic, normalized=/v1/messages
目标 URL: https://api.anthropic.com/v1/messages ✅
```
```

### 兼容性矩阵

| 功能 | Gateway 支持 | 测试状态 | 备注 |
|------|-------------|---------|------|
| Messages（非流式） | Expected | Expected | `response.usage` → AnthropicParser |
| Messages（流式） | Expected | Expected | SSE `message_stop` / `message_delta` → Usage |
| Cache 统计 | Expected | Expected | `cache_read_input_tokens`, `cache_creation_input_tokens` |
| System Prompt | Expected | Expected | Request body 透传 |
| Tool Use | Expected | Expected | 同上 |
| Vision（图片输入） | Expected | Expected | 同上 |

### 验证记录（待填写）

```
SDK:          anthropic (Python)
Version:      TBD
Base URL:     http://127.0.0.1:8910/anthropic
Test 1:       Messages (非流式) → Result: Pending
Test 2:       Messages (流式)   → Result: Pending
Test 3:       Cache 统计验证    → Result: Pending
Usage Stats:  Pending
Date:         TBD
```

---

## 3. LangChain (OpenAI)

### 配置方式

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    openai_api_base="http://127.0.0.1:8910/openai/v1",
    openai_api_key="sk-xxx",
    model="gpt-4o",
)
```

### 兼容性矩阵

| 功能 | Gateway 支持 | 测试状态 |
|------|-------------|---------|
| Chat（非流式） | Expected | Expected |
| Chat（流式） | Expected | Expected |
| Embeddings | Expected | Expected |
| Function Calling | Expected | Expected |

### 验证记录（待填写）

```
SDK:          langchain-openai (Python)
Version:      TBD
Base URL:     http://127.0.0.1:8910/openai/v1
Test 1:       invoke (非流式) → Result: Pending
Test 2:       stream (流式)   → Result: Pending
Date:         TBD
```

---

## 4. LangChain (Anthropic)

### 配置方式

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    anthropic_api_base="http://127.0.0.1:8910/anthropic",
    anthropic_api_key="sk-ant-xxx",
    model="claude-sonnet-4-20250514",
)
```

### 兼容性矩阵

| 功能 | Gateway 支持 | 测试状态 |
|------|-------------|---------|
| Chat（非流式） | Expected | Expected |
| Chat（流式） | Expected | Expected |

### 验证记录（待填写）

```
SDK:          langchain-anthropic (Python)
Version:      TBD
Base URL:     http://127.0.0.1:8910/anthropic
Test 1:       invoke (非流式) → Result: Pending
Test 2:       stream (流式)   → Result: Pending
Date:         TBD
```

---

## 5. LlamaIndex

### 配置方式

```python
from llama_index.llms.openai import OpenAI

llm = OpenAI(
    api_base="http://127.0.0.1:8910/openai/v1",
    api_key="sk-xxx",
    model="gpt-4o",
)
```

### 兼容性矩阵

| 功能 | Gateway 支持 | 测试状态 |
|------|-------------|---------|
| Chat（非流式） | Expected | Expected |
| Chat（流式） | Expected | Expected |
| Embeddings | Expected | Expected |

### 验证记录（待填写）

```
SDK:          llama-index (Python)
Version:      TBD
Base URL:     http://127.0.0.1:8910/openai/v1
Test 1:       complete (非流式) → Result: Pending
Test 2:       stream_complete    → Result: Pending
Date:         TBD
```

---

## 6. Continue (VS Code / JetBrains 插件)

### 配置方式

在 `config.json` 中为每个 Model 配置 `apiBase`：

```json
{
  "models": [
    {
      "title": "GPT-4o",
      "provider": "openai",
      "model": "gpt-4o",
      "apiBase": "http://127.0.0.1:8910/openai/v1",
      "apiKey": "sk-xxx"
    },
    {
      "title": "Claude Sonnet",
      "provider": "anthropic",
      "model": "claude-sonnet-4-20250514",
      "apiBase": "http://127.0.0.1:8910/anthropic",
      "apiKey": "sk-ant-xxx"
    }
  ]
}
```

### 兼容性矩阵

| 功能 | Gateway 支持 | 测试状态 |
|------|-------------|---------|
| Chat（非流式） | Expected | Expected |
| Chat（流式） | Expected | Expected |
| 多 Provider 切换 | Expected | Expected |

### 验证记录（待填写）

```
Client:       Continue (VS Code)
Version:      TBD
OpenAI Base:  http://127.0.0.1:8910/openai/v1
Anthropic:    http://127.0.0.1:8910/anthropic
Test 1:       OpenAI Chat → Result: Pending
Test 2:       Anthropic Chat → Result: Pending
Date:         TBD
```

---

## 7. Cherry Studio

### 配置方式

Cherry Studio → 设置 → 模型服务 → 添加 Provider：

| 字段 | 值 |
|------|-----|
| Provider 名称 | OpenAI（或其他） |
| API Address | `http://127.0.0.1:8910/openai` |
| API Key | `sk-xxx`（透传模式）或留空（管理模式） |

### Base URL 说明

Cherry Studio 在 API Address 之后自动追加路径。

```
API Address: http://127.0.0.1:8910/openai/v1  ← 推荐（与 OpenAI SDK 一致）
API Address: http://127.0.0.1:8910/openai      ← 不推荐（路径缺 /v1）
```

对于 Anthropic Provider：
```
API Address: http://127.0.0.1:8910/anthropic    ← 推荐（不含 /v1，避免 double）
```

**P0 实测提示：** Cherry Studio 未在当前环境安装，路径行为待真实验证后确认。当前推荐基于 OpenAI SDK 和 Anthropic SDK 的实测结果推断。

### 兼容性矩阵

| 功能 | Gateway 支持 | 测试状态 |
|------|-------------|---------|
| 多 Provider（通过不同 Address） | Expected | Expected |
| Chat（非流式） | Expected | Expected |
| Chat（流式） | Expected | Expected |
| 多轮对话 | Expected | Expected |
| 图片输入 | Expected | Expected |

### 验证记录（待填写）

```
Client:       Cherry Studio
Version:      TBD
API Address:  http://127.0.0.1:8910/openai
Test 1:       Chat Completion (流式, OpenAI) → Result: Pending
Test 2:       Chat Completion (非流式, OpenAI) → Result: Pending
Test 3:       多 Provider 切换 (Anthropic) → Result: Pending
Date:         TBD
```

---

## 8. Open WebUI

### 配置方式

启动时设置环境变量：

```bash
# OpenAI
set OPENAI_API_BASE_URL=http://127.0.0.1:8910/openai/v1
set OPENAI_API_KEY=sk-xxx

# Anthropic
set ANTHROPIC_API_BASE_URL=http://127.0.0.1:8910/anthropic
set ANTHROPIC_API_KEY=sk-ant-xxx
```

或在 Admin Settings → Connections 中配置。

### 兼容性矩阵

| 功能 | Gateway 支持 | 测试状态 |
|------|-------------|---------|
| OpenAI Chat | Expected | Expected |
| Anthropic Chat | Expected | Expected |
| 多 Provider 切换 | Expected | Expected |
| RAG / 文件上传 | Expected | Expected |

### 验证记录（待填写）

```
Client:       Open WebUI
Version:      TBD
OpenAI Base:  http://127.0.0.1:8910/openai/v1
Anthropic:    http://127.0.0.1:8910/anthropic
Test 1:       OpenAI Chat → Result: Pending
Test 2:       Anthropic Chat → Result: Pending
Date:         TBD
```

---

## 汇总

| SDK / Client | 接入方式 | 测试状态 | 优先级 |
|-------------|---------|---------|--------|
| OpenAI Python SDK | `base_url` | Expected | P0（阶段 1 验证） |
| Anthropic Python SDK | `base_url` | Expected | P0（阶段 1 验证） |
| Cherry Studio | API Address | Expected | P0（阶段 1 验证） |
| Gemini API | `base_url` | Expected | P0（阶段 1 验证） |
| LangChain (OpenAI) | `openai_api_base` | Expected | P1（阶段 4） |
| LangChain (Anthropic) | `anthropic_api_base` | Expected | P1（阶段 4） |
| LlamaIndex | `api_base` | Expected | P1（阶段 4） |
| Continue | `apiBase` per model | Expected | P1（阶段 4） |
| Open WebUI | 环境变量 | Expected | P1（阶段 4） |

---

**本文档将在每个 SDK/Client 完成真实集成测试后更新状态和验证记录。**
