# TokenMonitor

AI Token 使用监控与费用分析工具 — Windows 桌面应用。

实时统计和分析电脑上所有 AI 客户端的 Token 消耗、费用、模型使用情况。

---

## 快速开始

### 第一步：安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate    # Windows

# 安装依赖
pip install -r requirements.txt
```

### 第二步：配置 API Key

TokenMonitor 以**透传模式**工作——你只需在 AI 客户端中像往常一样填入 API Key，软件不会存储你的密钥。

如果你希望通过环境变量统一管理密钥，复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 填入你的 API Key：

```env
DEEPSEEK_API_KEY=sk-your-deepseek-key
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GEMINI_API_KEY=your-gemini-key
OPENROUTER_API_KEY=sk-or-your-openrouter-key
```

> 支持的环境变量和获取地址见 [API Key 参考](#api-key-参考)。

### 第三步：启动软件

```bash
python -m src.main
```

启动后会出现：

| 界面 | 说明 |
|------|------|
| **主窗口** | 仪表盘、历史记录、模型管理、预算设置、系统设置 |
| **悬浮窗** | 屏幕右上角半透明小窗口，始终置顶，显示实时 Token 统计 |
| **系统托盘** | 右下角任务栏绿色 "T" 图标，右键弹出菜单 |

代理服务器默认监听 `127.0.0.1:8910`。

### 第四步：配置 AI 客户端

将客户端接入 TokenMonitor 有 **两种方式**。推荐使用 Gateway 模式。

#### Gateway 模式（推荐）

把客户端的 API 地址改为 TokenMonitor 的地址 + Provider 前缀：

| 客户端 | 配置位置 | 设置值 |
|--------|---------|--------|
| **Cherry Studio** | 设置 → 模型服务 → 添加提供商 | API 地址：`http://127.0.0.1:8910/openai` |
| **OpenAI SDK** | `base_url` 参数 | `http://127.0.0.1:8910/openai/v1` |
| **Anthropic SDK** | `base_url` 参数 | `http://127.0.0.1:8910/anthropic` |
| **Open WebUI** | 环境变量 | `OPENAI_API_BASE=http://127.0.0.1:8910/openai/v1` |

> API Key 照常在客户端中填写即可，TokenMonitor 会透传。

**Cherry Studio 具体操作：**

```
1. 打开 Cherry Studio → 左下角「设置」
2. 点击「模型服务」→「添加提供商」
3. 选择 OpenAI 兼容
4. API 地址填入：http://127.0.0.1:8910/openai
5. API Key 填入你的 DeepSeek Key（或其他 Key）
6. 点击「检查」→ 确认模型列表加载成功
7. 开始对话，TokenMonitor 自动拦截并统计
```

#### Proxy 模式（兼容）

将客户端的 HTTP 代理设为 `127.0.0.1:8910`：

| 客户端 | 操作 |
|--------|------|
| **Cherry Studio** | 设置 → 网络 → HTTP 代理 → `http://127.0.0.1:8910` |
| **Claude Code** | `set HTTP_PROXY=http://127.0.0.1:8910` |
| **Cursor / VSCode** | 设置搜索 "proxy" → 填入 `http://127.0.0.1:8910` |
| **Continue** | `config.json` 添加 `"proxy": "http://127.0.0.1:8910"` |

---

## 使用功能

### 主页仪表盘

- 6 张统计卡片：今日 Token、今日费用、本周 Token、本月 Token、本月费用、活跃模型
- 模型 Token 分布图：横向柱状图，按消耗量排列
- 最近请求列表：实时显示每条 API 请求的详情

数据随每次 API 调用自动刷新，悬浮窗同步更新。

### 历史记录

- 支持今天 / 最近 7 天 / 30 天 / 本月 / 自定义范围
- Token 趋势折线图 + 费用趋势折线图 + 每日柱状图
- 导出为 CSV 或 Excel 文件

### 模型管理

- 查看 / 添加 / 编辑 / 删除模型定价配置
- 首次运行自动预置 20+ 常见模型的价格
- 修改后点击「刷新价格」立即生效

### 预算管理

- 分别设置每日 / 每周 / 每月预算上限
- 可按 80% / 90% / 100% 三档触发系统通知提醒
- 进度条直观展示当前花费占比

### 系统设置

- **通用**：开机自启、关闭最小化到托盘
- **代理**：修改监听地址和端口
- **数据**：查看数据库路径、清除所有历史数据
- **显示**：悬浮窗宽高、语言切换（中文 / English）

### 悬浮窗

| 操作 | 效果 |
|------|------|
| 左键拖动 | 移动悬浮窗位置 |
| 左键单击（<5px） | 打开主窗口 |
| 鼠标悬浮 | 展开显示输入/输出/费用详情 |
| 右键单击 | 弹出菜单（打开主页 / 隐藏 / 退出） |

### 系统托盘

| 操作 | 效果 |
|------|------|
| 双击托盘图标 | 打开主窗口 |
| 右键托盘图标 | 菜单（打开主页 / 显示悬浮窗 / 设置 / 退出） |

### 退出程序

| 方式 | 效果 |
|------|------|
| 点击主窗口 ✕ | 最小化到托盘，**后台继续运行** |
| 右键托盘 → 退出 | **完全退出** |
| 右键悬浮窗 → 退出 | **完全退出** |

---

## 工作原理

```
AI 客户端发起请求
       │
       ▼
127.0.0.1:8910  ─── TokenMonitor 本地代理
       │
       ├─ Gateway 模式：/openai/... → Router 识别 Provider
       │                              → PathAdapter 归一化路径
       │                              → EndpointResolver 确定目标 URL
       │
       ├─ Proxy 模式：完整 URL → 匹配 AI API 域名
       │
       ▼
转发到真实 API（如 api.deepseek.com）
       │
       ▼
接收响应 → Parser 提取 Token 用量
       │
       ▼
CostCalculator 计算费用 → SQLite 存储
       │
       ▼
EventBus 推送 → UI 实时刷新（主窗口 + 悬浮窗）
       │
       ▼
响应返回客户端（用户无感知）
```

---

## 支持的 AI 提供商

| Provider | 非流式 | 流式 (SSE) | 缓存 Token | 格式 |
|----------|--------|-----------|-----------|------|
| OpenAI | ✅ | ✅ | cached_tokens | Chat Completions |
| DeepSeek | ✅ | ✅ | — | OpenAI 兼容 |
| Anthropic | ✅ | ✅ | cache_read/write | Messages API |
| Gemini | ✅ | ✅ | — | GenerateContent |
| OpenRouter | ✅ | — | — | OpenAI 兼容 |
| CC-Switch | ✅ | — | — | OpenAI 兼容 |
| OpenAI 兼容 | ✅ | ✅ | — | vLLM / Ollama / Groq 等 |

---

## 当前 Gateway 路由

| 请求前缀 | 转发目标 | 说明 |
|---------|---------|------|
| `/openai/` | `api.deepseek.com` | OpenAI 协议 → DeepSeek 后端 |
| `/anthropic/` | `api.anthropic.com` | Anthropic 协议直通 |

> 在客户端中配置 `http://127.0.0.1:8910/openai` 即可将请求路由到 DeepSeek。

---

## API Key 参考

| 环境变量 | 对应 Provider | 获取地址 |
|----------|--------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek | https://platform.deepseek.com/api_keys |
| `OPENAI_API_KEY` | OpenAI | https://platform.openai.com/api-keys |
| `ANTHROPIC_API_KEY` | Anthropic | https://console.anthropic.com/settings/keys |
| `GEMINI_API_KEY` | Gemini | https://aistudio.google.com/app/apikey |
| `OPENROUTER_API_KEY` | OpenRouter | https://openrouter.ai/keys |

---

## 查看日志

```bash
# 实时跟踪
tail -f token_monitor.log

# 查看最近 100 行
tail -100 token_monitor.log

# 只看错误
grep ERROR token_monitor.log

# 只看代理请求
grep "Gateway" token_monitor.log
```

日志级别可在 `config.yaml` 中调整（DEBUG / INFO / WARNING / ERROR）。

---

## 开发

```bash
# 运行测试
python -m unittest discover -s tests -v

# 打包为单文件 exe
pip install pyinstaller
pyinstaller token_monitor.spec
```

### 项目结构

```
tokenMonitor/
├── src/
│   ├── main.py                 # 程序入口
│   ├── core/                   # 配置、事件总线、应用生命周期
│   ├── proxy/                  # 代理服务器、Router、PathAdapter、EndpointResolver
│   ├── parser/                 # Usage 解析器（各 Provider）
│   ├── statistics/             # 统计引擎、费用计算
│   ├── database/               # SQLite 数据层
│   ├── services/               # 业务服务层
│   ├── ui/                     # PyQt6 界面（仪表盘/历史/模型/预算/设置/悬浮窗/托盘）
│   └── utils/                  # 日志、Token 计数、国际化
├── tests/                      # 单元测试
├── docs/                       # 架构文档、兼容性报告
├── config.yaml                 # 应用配置
├── requirements.txt            # Python 依赖
└── token_monitor.spec          # PyInstaller 打包配置
```

---

## 许可

MIT
