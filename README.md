# TokenMonitor

AI Token 使用监控与费用分析工具 — Windows 桌面应用。

实时统计和分析电脑上所有 AI 客户端的 Token 消耗、费用、模型使用情况。

本项目还不成熟，目前只完成了DS再cherry studio上的适配
---

## 环境配置

### API Keys

TokenMonitor 通过环境变量读取 API Keys。复制 `.env.example` 为 `.env` 并填入你的密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
DEEPSEEK_API_KEY=sk-your-key-here
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

支持的环境变量：

| 变量 | Provider | 获取地址 |
|------|----------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek | https://platform.deepseek.com/api_keys |
| `OPENAI_API_KEY` | OpenAI | https://platform.openai.com/api-keys |
| `ANTHROPIC_API_KEY` | Anthropic | https://console.anthropic.com/settings/keys |
| `GEMINI_API_KEY` | Gemini | https://aistudio.google.com/app/apikey |
| `OPENROUTER_API_KEY` | OpenRouter | https://openrouter.ai/keys |

> ⚠️ `.env` 文件已在 `.gitignore` 中排除，不会提交到 Git。不要将 API Keys 硬编码到代码中。

---

## 启动与退出

### 启动

```bash
# 1. 安装依赖（首次运行）
pip install -r requirements.txt

# 2. 启动程序
python -m src.main
```

启动后会出现：
- **主窗口** — 仪表盘、历史记录、模型管理等完整界面
- **悬浮窗** — 屏幕右上角的半透明小窗口，始终置顶显示实时统计
- **系统托盘图标** — 右下角任务栏的绿色 "T" 图标

### 退出

程序有三种退出方式：

| 方式 | 操作 | 效果 |
|------|------|------|
| 关闭窗口 | 点击主窗口 ✕ | 最小化到系统托盘，**后台继续运行** |
| 托盘退出 | 右键托盘图标 → 退出 | **完全退出**程序 |
| 悬浮窗退出 | 右键悬浮窗 → 退出 | **完全退出**程序 |
| 强制结束 | 任务管理器结束 python.exe | **完全退出**（不推荐） |

> **注意：** 直接点击主窗口关闭按钮默认不会退出程序，而是最小化到托盘继续运行。如需关闭此行为，在「设置 → 通用 → 关闭时最小化到托盘」取消勾选。

---

## 功能

- **实时 Token 统计** — 通过本地代理拦截所有 AI API 请求，解析 usage 数据
- **费用计算** — 按模型定价自动计算费用，支持各模型独立配置价格
- **流式输出支持** — 完整兼容 SSE (Server-Sent Events)，流式响应中提取 usage
- **仪表盘** — 今日/本周/本月 Token 和费用概览、模型分布图、最近请求列表
- **历史记录** — 按日期范围查看趋势图（折线图/柱状图），支持 CSV 和 Excel 导出
- **模型管理** — 自定义 Provider/模型/价格的增删改查
- **预算管理** — 每日/每周/每月预算，达到 80%/90%/100% 时触发提醒
- **悬浮窗** — 桌面置顶、半透明、可拖拽，显示当前活跃模型和今日 Token
- **系统托盘** — 右键菜单快速访问仪表盘、悬浮窗、设置、退出
- **中英文切换** — 设置中一键切换界面语言
- **深色主题** — 现代化暗色 UI，风格参考 Cursor / Claude Desktop

---

## 支持的 AI 提供商

- OpenAI API（Chat Completions / Responses）
- Anthropic Claude API（Messages）
- Google Gemini API（GenerateContent）
- DeepSeek API
- OpenRouter API
- cc-switch 中转 API
- OpenAI 兼容 API（vLLM、Ollama、Mistral、Groq 等）

---

## 支持的 AI 客户端

- Cherry Studio
- Claude Code
- Continue
- Open WebUI
- Cursor
- VSCode AI 插件
- 所有使用 HTTP API 的 AI 客户端

---

## 配置客户端代理

将 AI 客户端的 HTTP 代理设置为 `http://127.0.0.1:8910`。

### Cherry Studio
设置 → 网络 → 代理 → HTTP 代理：`http://127.0.0.1:8910`

### Claude Code
```bash
set HTTP_PROXY=http://127.0.0.1:8910
set HTTPS_PROXY=http://127.0.0.1:8910
```

### Cursor / VSCode
设置 → 搜索 "proxy" → 填入 `http://127.0.0.1:8910`

### Continue
在 `config.json` 中添加：`"proxy": "http://127.0.0.1:8910"`

### Open WebUI
启动时添加环境变量：
```bash
set OPENAI_API_BASE=http://127.0.0.1:8910/openai/v1
```

---

## 项目架构

```
AI 客户端 → Gateway(127.0.0.1:8910) → Router/EndpointResolver → 真实API → 解析Usage → SQLite → UI刷新
                                        ↓
                                  Provider Identity 分离
                                  (client_type vs actual_provider)
```

### 目录结构

```
tokenMonitor/
├── src/
│   ├── main.py                 # 程序入口
│   ├── core/                   # 核心：配置、事件总线、启动引导
│   ├── proxy/                  # Gateway 服务器、Router、EndpointResolver
│   ├── parser/                 # Usage 解析器（各 Provider）
│   ├── statistics/             # 统计引擎、费用计算
│   ├── database/               # SQLite 数据库层
│   ├── services/               # 业务服务层
│   ├── ui/                     # PyQt6 界面
│   │   ├── dashboard/          # 仪表盘
│   │   ├── history/            # 历史记录
│   │   ├── models_page/        # 模型管理
│   │   ├── budget/             # 预算管理
│   │   ├── settings/           # 系统设置
│   │   └── widgets/            # 可复用组件
│   └── utils/                  # 工具：日志、Token计数、国际化
├── tests/                      # 测试（集成 + 单元）
├── tools/                      # 诊断工具（Path Discovery）
├── docs/                       # 架构、兼容性、验证报告
├── config.yaml                 # 配置文件
├── .env.example                # 环境变量模板
├── requirements.txt            # Python 依赖
└── token_monitor.spec          # PyInstaller 打包配置
```

---

## 开发

```bash
# 运行测试
python -m unittest discover -s tests -v

# 打包为单文件 exe
pip install pyinstaller
pyinstaller token_monitor.spec
```

---

## 许可

MIT
