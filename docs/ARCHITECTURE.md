# TokenMonitor Architecture Document

## 1. Project Directory Structure

```
tokenMonitor/
├── CLAUDE.md                     # Project guidelines
├── README.md                     # Project overview
├── requirements.txt              # Python dependencies
├── config.yaml                   # Application configuration
├── token_monitor.spec            # PyInstaller spec
├── docs/
│   ├── ARCHITECTURE.md           # This document
│   ├── ROADMAP.md                # Development roadmap
│   └── TASKS.md                  # Task tracking
├── src/
│   ├── __init__.py
│   ├── main.py                   # Application entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── app.py                # Application bootstrap & lifecycle
│   │   ├── event_bus.py          # Event system for real-time updates
│   │   └── config.py             # Configuration manager (config.yaml)
│   ├── proxy/
│   │   ├── __init__.py
│   │   ├── server.py             # HTTP/HTTPS proxy server (aiohttp)
│   │   ├── handler.py            # Request handler & response interceptor
│   │   ├── forwarder.py          # Request forwarding to real API endpoints
│   │   └── sse_handler.py        # SSE stream parser & relay
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract ProviderParser interface
│   │   ├── openai.py             # OpenAI / Compatible API parser
│   │   ├── anthropic.py          # Anthropic Claude API parser
│   │   ├── gemini.py             # Google Gemini API parser
│   │   ├── deepseek.py           # DeepSeek API parser
│   │   ├── openrouter.py         # OpenRouter API parser
│   │   ├── ccswitch.py           # cc-switch API parser
│   │   └── registry.py           # Parser registry (auto-detection)
│   ├── statistics/
│   │   ├── __init__.py
│   │   ├── engine.py             # Statistics aggregation engine
│   │   └── calculator.py         # Cost calculator
│   ├── database/
│   │   ├── __init__.py
│   │   ├── manager.py            # DatabaseManager (SQLite)
│   │   ├── models.py             # SQLAlchemy / Pydantic models
│   │   ├── repository.py         # Repository pattern for DB access
│   │   └── migrations.py         # Schema migrations
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py        # MainWindow (PyQt6)
│   │   ├── theme.py              # Dark theme / style manager
│   │   ├── dashboard/
│   │   │   ├── __init__.py
│   │   │   └── page.py           # Dashboard page
│   │   ├── history/
│   │   │   ├── __init__.py
│   │   │   └── page.py           # History page with charts
│   │   ├── models_page/
│   │   │   ├── __init__.py
│   │   │   └── page.py           # Model management page
│   │   ├── budget/
│   │   │   ├── __init__.py
│   │   │   └── page.py           # Budget management page
│   │   ├── settings/
│   │   │   ├── __init__.py
│   │   │   └── page.py           # Settings page
│   │   ├── floating.py           # Floating widget (overlay)
│   │   ├── tray.py               # System tray manager
│   │   └── widgets/
│   │       ├── __init__.py
│   │       ├── token_card.py     # Token stat card widget
│   │       ├── chart_widgets.py  # Chart wrapper widgets
│   │       └── request_table.py  # Request log table widget
│   ├── services/
│   │   ├── __init__.py
│   │   ├── proxy_service.py      # Proxy lifecycle service
│   │   └── stats_service.py      # Statistics query service
│   └── utils/
│       ├── __init__.py
│       ├── logger.py             # Logging configuration
│       └── token_counter.py      # tiktoken-based token counter (fallback)
├── tests/
│   ├── __init__.py
│   ├── test_parsers.py
│   ├── test_statistics.py
│   ├── test_database.py
│   └── test_proxy.py
└── resources/
    ├── icon.ico                  # Application icon
    ├── icon.png                  # Tray icon
    └── styles/
        └── dark.qss             # Dark theme stylesheet
```

## 2. Technology Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  MainWindow  │  │  FloatingWin │  │  SystemTray    │  │
│  │  (PyQt6)     │  │  (PyQt6)     │  │  (PyQt6)       │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                 │                  │           │
├─────────┼─────────────────┼──────────────────┼───────────┤
│         │          Event Bus (Signals/Slots)  │           │
├─────────┼─────────────────┼──────────────────┼───────────┤
│         │           Service Layer              │           │
│  ┌──────┴──────────────────┴──────────────────┴────────┐  │
│  │              StatisticsService                      │  │
│  │              ProxyService                           │  │
│  └──────┬──────────────────────────────────────┬───────┘  │
│         │                                      │          │
├─────────┼──────────────────────────────────────┼──────────┤
│         │           Business Layer             │          │
│  ┌──────┴──────────┐  ┌──────────────┐  ┌─────┴───────┐  │
│  │  StatisticsEngine│  │ CostCalculator│  │ UsageParser │  │
│  └──────┬──────────┘  └──────┬───────┘  └─────┬───────┘  │
│         │                    │                │           │
├─────────┼────────────────────┼────────────────┼───────────┤
│         │           Data Layer                 │           │
│  ┌──────┴────────────────────┴────────────────┴─────────┐  │
│  │                  Repository                          │  │
│  │              DatabaseManager (SQLite)                 │  │
│  └──────────────────────────────────────────────────────┘  │
├───────────────────────────────────────────────────────────┤
│                    Infrastructure                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │  Proxy Server │  │  SSE Handler │  │  Token Counter│   │
│  │  (aiohttp)    │  │  (aiohttp)   │  │  (tiktoken)   │   │
│  └──────────────┘  └──────────────┘  └───────────────┘   │
└───────────────────────────────────────────────────────────┘
```

## 3. Data Flow Diagram

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ AI Client │────▶│ Local Proxy  │────▶│ Real API     │────▶│ AI Provider  │
│ (Cursor,  │     │ 127.0.0.1   │     │ Endpoint     │     │ (OpenAI,etc) │
│  CC, etc) │     │ :7890       │     │              │     │              │
└──────────┘     └──────┬───────┘     └──────┬───────┘     └──────────────┘
                        │                    │
                        │ ◀── Response ──────┘ (SSE / JSON)
                        │
                  ┌─────┴──────┐
                  │  Intercept  │
                  │  Response   │
                  └─────┬──────┘
                        │
                  ┌─────┴──────┐
                  │ UsageParser │──── Provider detection
                  │ .parse()    │──── JSON body parse
                  └─────┬──────┘──── SSE event parse
                        │
                  ┌─────┴──────┐
                  │CostCalculator│─── Input price × tokens
                  │ .calculate() │─── Output price × tokens
                  └─────┬──────┘
                        │
                  ┌─────┴──────────┐
                  │StatisticsEngine │─── Update daily_stats
                  │ .record()       │─── Insert request_logs
                  └─────┬──────────┘
                        │
                  ┌─────┴──────┐
                  │  EventBus   │─── emit("stats_updated")
                  │  .emit()    │
                  └─────┬──────┘
                        │
            ┌───────────┼───────────┐
            │           │           │
      ┌─────┴────┐ ┌───┴────┐ ┌───┴──────┐
      │Dashboard │ │History │ │Floating  │
      │Refresh   │ │Update  │ │Widget    │
      └──────────┘ └────────┘ └──────────┘
```

### SSE Stream Processing

```
SSE Response Body:
  data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n
  data: {"choices":[{"delta":{"content":" world"}}]}\n\n
  data: [DONE]\n\n
                      │
                      ▼
            ┌─────────────────┐
            │ SSEHandler      │
            │ .parse_stream() │
            └────────┬────────┘
                     │
          ┌──────────┼──────────┐
          │          │          │
     Forward to   Buffer     Parse
     Client       chunks     usage from
                             last chunk
```

## 4. SQLite Schema

```sql
-- request_logs: Every individual API request
CREATE TABLE IF NOT EXISTS request_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       REAL NOT NULL,          -- Unix timestamp (UTC)
    provider        TEXT NOT NULL,          -- openai, anthropic, gemini, deepseek, etc.
    model           TEXT NOT NULL,          -- gpt-4, claude-sonnet-4-20250514, etc.
    endpoint        TEXT,                   -- Full API endpoint URL
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens   INTEGER DEFAULT 0,  -- Anthropic cache read
    cache_write_tokens  INTEGER DEFAULT 0,  -- Anthropic cache write
    cost            REAL NOT NULL DEFAULT 0.0,
    currency        TEXT NOT NULL DEFAULT 'USD',
    latency_ms      REAL,                   -- Request latency in milliseconds
    status_code     INTEGER,                -- HTTP status code
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_request_logs_timestamp ON request_logs(timestamp);
CREATE INDEX idx_request_logs_provider ON request_logs(provider);
CREATE INDEX idx_request_logs_model ON request_logs(model);
CREATE INDEX idx_request_logs_date ON request_logs(date(timestamp));

-- daily_stats: Aggregated per-model daily statistics
CREATE TABLE IF NOT EXISTS daily_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,          -- YYYY-MM-DD
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    request_count   INTEGER NOT NULL DEFAULT 0,
    cost            REAL NOT NULL DEFAULT 0.0,
    currency        TEXT NOT NULL DEFAULT 'USD',
    UNIQUE(date, provider, model)
);

CREATE INDEX idx_daily_stats_date ON daily_stats(date);
CREATE INDEX idx_daily_stats_model ON daily_stats(model);

-- model_configs: Pricing and configuration for each model
CREATE TABLE IF NOT EXISTS model_configs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider        TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    display_name    TEXT,
    api_url         TEXT,
    input_price     REAL NOT NULL DEFAULT 0.0,   -- Per 1M tokens
    output_price    REAL NOT NULL DEFAULT 0.0,   -- Per 1M tokens
    cache_read_price    REAL DEFAULT 0.0,
    cache_write_price   REAL DEFAULT 0.0,
    currency        TEXT NOT NULL DEFAULT 'USD',
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(provider, model_name)
);

-- Pre-populate common model prices
-- OpenAI models: input_price/output_price per 1M tokens
-- gpt-4o: $2.50/$10.00
-- gpt-4o-mini: $0.15/$0.60
-- o4-mini: $1.10/$4.40
-- etc.

-- budget_config: User budget settings
CREATE TABLE IF NOT EXISTS budget_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_type     TEXT NOT NULL,          -- daily, weekly, monthly
    amount          REAL NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    notify_80       INTEGER NOT NULL DEFAULT 1,
    notify_90       INTEGER NOT NULL DEFAULT 1,
    notify_100      INTEGER NOT NULL DEFAULT 1,
    enabled         INTEGER NOT NULL DEFAULT 1
);

-- settings: Application key-value settings
CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Default settings
INSERT OR IGNORE INTO settings (key, value) VALUES
    ('proxy_port', '7890'),
    ('proxy_host', '127.0.0.1'),
    ('startup_auto_run', '0'),
    ('close_to_tray', '1'),
    ('show_floating', '1'),
    ('theme', 'dark'),
    ('db_path', 'token_monitor.db'),
    ('first_run', '1');
```

## 5. Core Class Design

### 5.1 Proxy Layer

```python
# proxy/server.py
class ProxyServer:
    """Local HTTP/HTTPS proxy server using aiohttp."""
    host: str
    port: int
    app: web.Application
    runner: web.AppRunner

    async def start() -> None
    async def stop() -> None
    async def handle_request(request: web.Request) -> web.StreamResponse

# proxy/handler.py
class RequestHandler:
    """Intercepts, forwards, and parses API responses."""
    parser_registry: ParserRegistry
    calculator: CostCalculator
    engine: StatisticsEngine

    async def handle(request: web.Request) -> web.StreamResponse
    async def _forward(request: web.Request, target_url: str) -> Response
    async def _process_response(response, provider, model) -> UsageData

# proxy/forwarder.py
class RequestForwarder:
    """Forwards requests to real API endpoints via httpx."""
    client: httpx.AsyncClient

    async def forward(request: web.Request, url: str) -> httpx.Response
    async def forward_stream(request: web.Request, url: str) -> AsyncIterator[bytes]

# proxy/sse_handler.py
class SSEHandler:
    """Parses and relays SSE streams, extracts usage from final chunk."""
    async def relay(source: AsyncIterator, target: web.StreamResponse) -> UsageData
```

### 5.2 Parser Layer

```python
# parser/base.py
@dataclass
class UsageData:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: float = 0.0

class ProviderParser(ABC):
    """Abstract base for all provider parsers."""
    provider_name: str

    @abstractmethod
    def can_parse(self, url: str, headers: dict) -> bool

    @abstractmethod
    def parse_usage(self, response_body: dict) -> UsageData | None

    @abstractmethod
    def parse_stream_chunk(self, chunk: dict) -> UsageData | None

    def extract_model(self, request_body: dict, response_body: dict) -> str

# parser/openai.py
class OpenAIParser(ProviderParser):
    """Parses OpenAI Chat Completions / Responses API usage."""
    provider_name = "openai"
    # Parses: response["usage"] -> {prompt_tokens, completion_tokens, total_tokens}
    # Also handles OpenAI-Compatible APIs (vLLM, Ollama, etc.)

# parser/anthropic.py
class AnthropicParser(ProviderParser):
    """Parses Anthropic Messages API usage."""
    provider_name = "anthropic"
    # Parses: response["usage"] -> {input_tokens, output_tokens}
    # Handles: cache_read_input_tokens, cache_creation_input_tokens

# parser/gemini.py
class GeminiParser(ProviderParser):
    """Parses Google Gemini API usage."""
    provider_name = "gemini"
    # Parses: response["usageMetadata"] -> {promptTokenCount, candidatesTokenCount, totalTokenCount}

# parser/deepseek.py
class DeepSeekParser(ProviderParser):
    """Parses DeepSeek API usage (OpenAI-compatible)."""
    provider_name = "deepseek"
    # Uses OpenAI format with DeepSeek-specific URL detection

# parser/registry.py
class ParserRegistry:
    """Registry of all parsers with auto-detection logic."""
    parsers: list[ProviderParser]

    def register(parser: ProviderParser) -> None
    def detect(url: str, headers: dict, body: dict) -> ProviderParser | None
    def parse_usage(response_body: dict, provider: str) -> UsageData | None
```

### 5.3 Statistics Layer

```python
# statistics/engine.py
@dataclass
class DailyStats:
    date: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int
    cost: float

@dataclass
class StatsSummary:
    today_tokens: int
    week_tokens: int
    month_tokens: int
    today_cost: float
    month_cost: float
    active_models: list[str]
    top_models: list[tuple[str, int]]  # (model, tokens)

class StatisticsEngine:
    """Core statistics aggregation engine."""
    repository: Repository
    event_bus: EventBus

    async def record(usage: UsageData) -> None
    async def get_daily_stats(date: str) -> list[DailyStats]
    async def get_range_stats(start: str, end: str) -> list[DailyStats]
    async def get_summary() -> StatsSummary
    async def get_model_breakdown(date: str) -> list[tuple[str, float]]  # (model, %)

# statistics/calculator.py
class CostCalculator:
    """Calculates cost based on model pricing."""
    repository: Repository

    def calculate(model: str, input_tokens: int, output_tokens: int,
                  cache_read: int = 0, cache_write: int = 0) -> float
    async def get_model_price(model: str) -> tuple[float, float] | None
    async def update_prices() -> None  # Sync with model_configs table
```

### 5.4 Database Layer

```python
# database/manager.py
class DatabaseManager:
    """Singleton SQLite database manager."""
    db_path: str
    _connection: sqlite3.Connection

    def get_connection() -> sqlite3.Connection
    def close() -> None
    def execute(sql: str, params: tuple = None) -> sqlite3.Cursor
    def execute_many(sql: str, params_list: list[tuple]) -> sqlite3.Cursor
    def initialize_schema() -> None  # Create tables & defaults

# database/repository.py
class Repository:
    """Data access layer abstracting SQL queries."""
    db: DatabaseManager

    # Request Logs
    def insert_request_log(usage: UsageData) -> int
    def get_request_logs(limit: int = 100, offset: int = 0) -> list[dict]
    def get_request_logs_by_date(date: str) -> list[dict]

    # Daily Stats
    def upsert_daily_stats(stats: DailyStats) -> None
    def get_daily_stats(date: str) -> list[dict]
    def get_stats_range(start: str, end: str) -> list[dict]

    # Model Configs
    def get_all_models() -> list[dict]
    def get_model(provider: str, model_name: str) -> dict | None
    def insert_model(config: dict) -> int
    def update_model(id: int, config: dict) -> None
    def delete_model(id: int) -> None
    def get_enabled_models() -> list[dict]

    # Budget
    def get_budget(budget_type: str) -> dict | None
    def set_budget(budget_type: str, amount: float) -> None

    # Settings
    def get_setting(key: str, default: str = None) -> str
    def set_setting(key: str, value: str) -> None
    def get_all_settings() -> dict
```

### 5.5 UI Layer

```python
# ui/main_window.py
class MainWindow(QMainWindow):
    """Main application window with sidebar navigation."""
    dashboard_page: DashboardPage
    history_page: HistoryPage
    models_page: ModelsPage
    budget_page: BudgetPage
    settings_page: SettingsPage
    floating_widget: FloatingWidget
    tray_manager: TrayManager

    def closeEvent(event) -> None  # Minimize to tray instead of close

# ui/dashboard/page.py
class DashboardPage(QWidget):
    """Dashboard showing real-time token/cost overview."""
    # Widgets: TokenCard x4, ModelPieChart, RecentRequestsTable
    def refresh() -> None

# ui/history/page.py
class HistoryPage(QWidget):
    """History view with charts and date range selection."""
    # Widgets: LineChart, BarChart, DateRangePicker, ExportButtons

# ui/models_page/page.py
class ModelsPage(QWidget):
    """Model configuration management."""
    # Widgets: ModelTable, AddEditDialog, ImportExportButtons

# ui/budget/page.py
class BudgetPage(QWidget):
    """Budget settings and progress tracking."""
    # Widgets: BudgetInputs, ProgressBars, NotificationSettings

# ui/settings/page.py
class SettingsPage(QWidget):
    """Application settings."""
    # Widgets: SettingGroups (General, Proxy, Display, Data)

# ui/floating.py
class FloatingWidget(QWidget):
    """Desktop overlay floating widget (220x70)."""
    # Always on top, frameless, rounded, semi-transparent
    # Shows: active model, today's token count
    # Hover: expands to show details
    # Click: opens main window

# ui/tray.py
class TrayManager:
    """System tray icon and context menu."""
    tray_icon: QSystemTrayIcon
    def show_notification(title: str, message: str) -> None

# ui/theme.py
class ThemeManager:
    """Dark theme style manager."""
    def apply_theme(app: QApplication) -> None
    def get_stylesheet() -> str
```

### 5.6 Services Layer

```python
# services/proxy_service.py
class ProxyService:
    """Manages proxy server lifecycle."""
    server: ProxyServer
    config: AppConfig

    async def start() -> None
    async def stop() -> None
    def is_running() -> bool

# services/stats_service.py
class StatsService:
    """High-level statistics query service for UI."""
    engine: StatisticsEngine
    repository: Repository

    async def get_dashboard_data() -> dict  # All dashboard data in one call
    async def get_history_data(start, end) -> dict
    async def get_budget_status() -> dict
```

### 5.7 Core Layer

```python
# core/event_bus.py
class EventBus(QObject):
    """Qt signal-based event bus for decoupled communication."""
    stats_updated = pyqtSignal()
    budget_warning = pyqtSignal(int)  # percentage: 80, 90, 100
    proxy_status_changed = pyqtSignal(bool)  # running/stopped
    new_request = pyqtSignal(object)  # UsageData

# core/config.py
@dataclass
class AppConfig:
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 7890
    db_path: str = "token_monitor.db"
    startup_auto_run: bool = False
    close_to_tray: bool = True
    show_floating: bool = True
    theme: str = "dark"

class ConfigManager:
    """Loads/saves config from config.yaml and settings table."""
    def load() -> AppConfig
    def save(config: AppConfig) -> None
    def get(key: str) -> Any
    def set(key: str, value: Any) -> None
```

## 6. MVP Development Plan

### Phase 1: Core Infrastructure (Foundation)

**Goal:** Proxy works, usage parsed, data stored, costs calculated.

| Step | Task | Verification |
|------|------|-------------|
| 1.1 | requirements.txt with all dependencies | pip install succeeds |
| 1.2 | DatabaseManager + Schema init | Tables created in SQLite |
| 1.3 | Repository CRUD operations | Insert/query returns correct data |
| 1.4 | ConfigManager with config.yaml | Config loads/saves correctly |
| 1.5 | ProviderParser base + OpenAI parser | Parses real OpenAI response JSON |
| 1.6 | Anthropic, Gemini, DeepSeek parsers | Each parses its own response format |
| 1.7 | ParserRegistry with auto-detection | Detects provider from URL/headers |
| 1.8 | CostCalculator | Correct cost for known models |
| 1.9 | StatisticsEngine | Aggregates usage correctly |
| 1.10 | EventBus | Signals emit and receive |
| 1.11 | ProxyServer (HTTP forward + intercept) | curl through proxy, usage recorded |
| 1.12 | SSE streaming support | Streaming responses relayed correctly |
| 1.13 | Logging setup | Logs written to file |

### Phase 2: Main UI

**Goal:** Full main window with all pages functional.

| Step | Task | Verification |
|------|------|-------------|
| 2.1 | QApplication bootstrap + theme | Dark window appears |
| 2.2 | MainWindow with sidebar navigation | Clicking nav switches pages |
| 2.3 | Dashboard page with stat cards | Shows today/week/month stats |
| 2.4 | Dashboard charts (pie chart) | Model distribution renders |
| 2.5 | Dashboard request table | Recent requests list updates |
| 2.6 | History page with date picker | Filter and display stats |
| 2.7 | History charts (line/bar) | PyQtGraph charts render |
| 2.8 | Models page CRUD | Add/edit/delete models |
| 2.9 | Budget page with progress bars | Budget tracking works |
| 2.10 | Settings page | All settings persist |

### Phase 3: Desktop Integration

**Goal:** System tray, floating widget, real-time updates.

| Step | Task | Verification |
|------|------|-------------|
| 3.1 | SystemTray icon + menu | Tray appears, menu works |
| 3.2 | Minimize to tray on close | Close → tray, not exit |
| 3.3 | FloatingWidget basic display | 220x70 window, always on top |
| 3.4 | FloatingWidget hover expand | Mouse hover shows details |
| 3.5 | FloatingWidget click actions | Left/right click works |
| 3.6 | Wire EventBus to UI refresh | New request → dashboard updates |
| 3.7 | Wire EventBus to floating widget | New request → floating updates |
| 3.8 | Budget notifications | 80/90/100% triggers notification |

### Phase 4: Polish & Package

**Goal:** Production-ready single exe.

| Step | Task | Verification |
|------|------|-------------|
| 4.1 | config.yaml defaults | Fresh install works |
| 4.2 | CSV/Excel export | Export produces valid files |
| 4.3 | Token counter fallback (tiktoken) | Counts tokens without usage field |
| 4.4 | Error handling review | No bare except: pass |
| 4.5 | Unit tests for parsers | All parsers tested |
| 4.6 | Unit tests for statistics | Aggregation tested |
| 4.7 | Unit tests for database | CRUD tested |
| 4.8 | PyInstaller spec file | Builds single exe |
| 4.9 | README with install/usage docs | Clear documentation |
