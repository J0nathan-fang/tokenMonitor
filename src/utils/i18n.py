"""
Internationalization (i18n) module for TokenMonitor.

Supports English (en) and Chinese (zh_CN).
Language preference is stored in the settings database.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("token_monitor.utils.i18n")

# ── Translation Maps ──────────────────────────────────────────

_ZH: dict[str, str] = {
    # App
    "app.title": "TokenMonitor - AI Token 使用监控",
    "app.version": "v1.0.0",

    # Sidebar navigation
    "nav.main": "🏠 主页",
    "nav.history": "📈 历史记录",
    "nav.models": "🤖 模型管理",
    "nav.budget": "💰 预算管理",
    "nav.settings": "⚙️ 系统设置",

    # Main page
    "main.title": "主页",
    "main.today_tokens": "今日 Token",
    "main.today_cost": "今日费用",
    "main.week_tokens": "本周 Token",
    "main.month_tokens": "本月 Token",
    "main.month_cost": "本月费用",
    "main.active_models": "今日活跃模型",
    "main.model_distribution": "模型分布 (今日)",
    "main.recent_requests": "最近请求",
    "main.in_out": "↑ {input} 入 | ↓ {output} 出",
    "main.requests_today": "{n} 次请求今日",
    "main.week_cost": "本周费用: {cost}",
    "main.month_cost_label": "本月费用: {cost}",

    # History
    "history.title": "历史记录",
    "history.range": "范围:",
    "history.range_today": "今天",
    "history.range_7days": "最近 7 天",
    "history.range_30days": "最近 30 天",
    "history.range_month": "本月",
    "history.range_custom": "自定义",
    "history.to": "至",
    "history.export_csv": "导出 CSV",
    "history.export_excel": "导出 Excel",
    "history.token_trend": "Token 趋势",
    "history.cost_trend": "费用趋势",
    "history.daily_breakdown": "每日 Token 明细",
    "history.tokens": "Tokens",
    "history.cost_usd": "费用 (USD)",

    # Models
    "models.title": "模型配置",
    "models.add": "+ 添加模型",
    "models.refresh": "刷新价格",
    "models.provider": "提供商",
    "models.model_name": "模型名称",
    "models.display_name": "显示名称",
    "models.api_url": "API 地址",
    "models.input_price": "输入价格/M",
    "models.output_price": "输出价格/M",
    "models.currency": "货币",
    "models.enabled": "启用",
    "models.actions": "",
    "models.edit": "编辑",
    "models.delete": "删除",
    "models.dialog_title_add": "添加模型",
    "models.dialog_title_edit": "编辑模型",
    "models.dialog_provider": "提供商:",
    "models.dialog_model_name": "模型名称:",
    "models.dialog_display_name": "显示名称:",
    "models.dialog_api_url": "API 地址:",
    "models.dialog_input_price": "输入价格:",
    "models.dialog_output_price": "输出价格:",
    "models.dialog_enabled": "启用:",
    "models.delete_confirm": "确定要删除 '{name}' 吗？",
    "models.delete_title": "删除模型",
    "models.validation_provider": "提供商不能为空。",
    "models.validation_model": "模型名称不能为空。",
    "models.validation_title": "验证失败",
    "models.yes": "是",
    "models.no": "否",
    "models.export_complete": "导出完成",
    "models.export_failed": "导出失败",

    # Budget
    "budget.title": "预算管理",
    "budget.daily": "每日预算",
    "budget.weekly": "每周预算",
    "budget.monthly": "每月预算",
    "budget.amount": "预算金额:",
    "budget.notify_at": "提醒阈值:",
    "budget.pct_80": "80%",
    "budget.pct_90": "90%",
    "budget.pct_100": "100%",
    "budget.current": "当前:",
    "budget.save_all": "保存所有预算",

    # Settings
    "settings.title": "系统设置",
    "settings.general": "通用",
    "settings.startup_auto": "开机自动启动",
    "settings.close_to_tray": "关闭时最小化到托盘",
    "settings.show_floating": "最小化时显示悬浮窗",
    "settings.proxy": "代理服务器",
    "settings.proxy_host": "主机:",
    "settings.proxy_port": "端口:",
    "settings.data": "数据",
    "settings.db_path": "数据库:",
    "settings.clear_data": "清除所有数据",
    "settings.display": "显示",
    "settings.theme": "主题:",
    "settings.language": "语言:",
    "settings.lang_en": "English",
    "settings.lang_zh": "中文",
    "settings.float_width": "悬浮窗宽度:",
    "settings.float_height": "悬浮窗高度:",
    "settings.save": "保存设置",
    "settings.saved": "设置已保存",
    "settings.saved_msg": "设置保存成功。\n部分更改可能需要重启后生效。",
    "settings.clear_confirm_title": "清除所有数据",
    "settings.clear_confirm_msg": "确定要删除所有 Token 历史记录和统计数据吗？\n此操作不可撤销。",
    "settings.cleared": "已清除",
    "settings.cleared_msg": "所有数据已清除。",
    "settings.missing_dep": "缺少依赖",
    "settings.missing_dep_msg": "openpyxl 未安装。请运行: pip install openpyxl",

    # Floating widget
    "floating.no_activity": "无活动",
    "floating.in": "入: {tokens}",
    "floating.out": "出: {tokens}",
    "floating.cost": "费用: {cost}",
    "floating.last": "上次: {time}",
    "floating.open_main": "打开主页",
    "floating.reset_today": "重置今日计数",
    "floating.hide_float": "隐藏悬浮窗",
    "floating.exit": "退出",

    # System tray
    "tray.tooltip": "TokenMonitor - AI Token 使用监控",
    "tray.open": "打开主页",
    "tray.show_float": "显示悬浮窗",
    "tray.settings": "设置",
    "tray.exit": "退出",
    "tray.notify_title": "TokenMonitor",
    "tray.notify_minimized": "程序已最小化到托盘。右键托盘图标可退出。",

    # Request table columns
    "table.time": "时间",
    "table.provider": "提供商",
    "table.model": "模型",
    "table.input": "输入",
    "table.output": "输出",
    "table.total": "总计",
    "table.cost": "费用",
    "table.latency": "延迟",

    # Export
    "export.csv_title": "导出 CSV",
    "export.csv_file": "token_history.csv",
    "export.csv_filter": "CSV 文件 (*.csv)",
    "export.excel_title": "导出 Excel",
    "export.excel_file": "token_history.xlsx",
    "export.excel_filter": "Excel 文件 (*.xlsx)",
    "export.complete": "导出完成",
    "export.msg": "数据已导出到 {path}",
    "export.failed": "导出失败",

    # Budget alerts
    "budget.alert_title": "预算提醒",
    "budget.alert_80": "已使用 {type} 预算的 80%",
    "budget.alert_90": "已使用 {type} 预算的 90%",
    "budget.alert_100": "已超出 {type} 预算！",
}

_EN: dict[str, str] = {
    # App
    "app.title": "TokenMonitor - AI Token Usage Monitor",
    "app.version": "v1.0.0",

    # Sidebar navigation
    "nav.main": "🏠 Main",
    "nav.history": "📈 History",
    "nav.models": "🤖 Models",
    "nav.budget": "💰 Budget",
    "nav.settings": "⚙️ Settings",

    # Main page
    "main.title": "Main",
    "main.today_tokens": "Today Tokens",
    "main.today_cost": "Today Cost",
    "main.week_tokens": "This Week Tokens",
    "main.month_tokens": "This Month Tokens",
    "main.month_cost": "This Month Cost",
    "main.active_models": "Active Models Today",
    "main.model_distribution": "Model Distribution (Today)",
    "main.recent_requests": "Recent Requests",
    "main.in_out": "↑ {input} in | ↓ {output} out",
    "main.requests_today": "{n} requests today",
    "main.week_cost": "Week cost: {cost}",
    "main.month_cost_label": "Month cost: {cost}",

    # History
    "history.title": "History",
    "history.range": "Range:",
    "history.range_today": "Today",
    "history.range_7days": "Last 7 Days",
    "history.range_30days": "Last 30 Days",
    "history.range_month": "This Month",
    "history.range_custom": "Custom",
    "history.to": "to",
    "history.export_csv": "Export CSV",
    "history.export_excel": "Export Excel",
    "history.token_trend": "Token Trend",
    "history.cost_trend": "Cost Trend",
    "history.daily_breakdown": "Daily Token Breakdown",
    "history.tokens": "Tokens",
    "history.cost_usd": "Cost (USD)",

    # Models
    "models.title": "Model Configurations",
    "models.add": "+ Add Model",
    "models.refresh": "Refresh Prices",
    "models.provider": "Provider",
    "models.model_name": "Model Name",
    "models.display_name": "Display Name",
    "models.api_url": "API URL",
    "models.input_price": "Input Price/M",
    "models.output_price": "Output Price/M",
    "models.currency": "Currency",
    "models.enabled": "Enabled",
    "models.actions": "",
    "models.edit": "Edit",
    "models.delete": "Delete",
    "models.dialog_title_add": "Add Model",
    "models.dialog_title_edit": "Edit Model",
    "models.dialog_provider": "Provider:",
    "models.dialog_model_name": "Model Name:",
    "models.dialog_display_name": "Display Name:",
    "models.dialog_api_url": "API URL:",
    "models.dialog_input_price": "Input Price:",
    "models.dialog_output_price": "Output Price:",
    "models.dialog_enabled": "Enabled:",
    "models.delete_confirm": "Are you sure you want to delete '{name}'?",
    "models.delete_title": "Delete Model",
    "models.validation_provider": "Provider is required.",
    "models.validation_model": "Model name is required.",
    "models.validation_title": "Validation",
    "models.yes": "Yes",
    "models.no": "No",
    "models.export_complete": "Export Complete",
    "models.export_failed": "Export Failed",

    # Budget
    "budget.title": "Budget Management",
    "budget.daily": "Daily Budget",
    "budget.weekly": "Weekly Budget",
    "budget.monthly": "Monthly Budget",
    "budget.amount": "Budget Amount:",
    "budget.notify_at": "Notify at:",
    "budget.pct_80": "80%",
    "budget.pct_90": "90%",
    "budget.pct_100": "100%",
    "budget.current": "Current:",
    "budget.save_all": "Save All Budgets",

    # Settings
    "settings.title": "Settings",
    "settings.general": "General",
    "settings.startup_auto": "Start automatically with Windows",
    "settings.close_to_tray": "Minimize to system tray on close",
    "settings.show_floating": "Show floating widget when minimized",
    "settings.proxy": "Proxy Server",
    "settings.proxy_host": "Host:",
    "settings.proxy_port": "Port:",
    "settings.data": "Data",
    "settings.db_path": "Database:",
    "settings.clear_data": "Clear All Data",
    "settings.display": "Display",
    "settings.theme": "Theme:",
    "settings.language": "Language:",
    "settings.lang_en": "English",
    "settings.lang_zh": "中文",
    "settings.float_width": "Floating Width:",
    "settings.float_height": "Floating Height:",
    "settings.save": "Save Settings",
    "settings.saved": "Settings Saved",
    "settings.saved_msg": "Settings saved successfully.\nSome changes may require a restart.",
    "settings.clear_confirm_title": "Clear All Data",
    "settings.clear_confirm_msg": "Are you sure you want to delete ALL token history and statistics?\nThis action cannot be undone.",
    "settings.cleared": "Cleared",
    "settings.cleared_msg": "All data has been cleared.",
    "settings.missing_dep": "Missing Dependency",
    "settings.missing_dep_msg": "openpyxl is not installed. Run: pip install openpyxl",

    # Floating widget
    "floating.no_activity": "No activity",
    "floating.in": "In: {tokens}",
    "floating.out": "Out: {tokens}",
    "floating.cost": "Cost: {cost}",
    "floating.last": "Last: {time}",
    "floating.open_main": "Open Main",
    "floating.reset_today": "Reset Today Counter",
    "floating.hide_float": "Hide Floating Window",
    "floating.exit": "Exit",

    # System tray
    "tray.tooltip": "TokenMonitor - AI Token Usage Monitor",
    "tray.open": "Open Main",
    "tray.show_float": "Show Floating Window",
    "tray.settings": "Settings",
    "tray.exit": "Exit",
    "tray.notify_title": "TokenMonitor",
    "tray.notify_minimized": "App minimized to tray. Right-click tray icon to exit.",

    # Request table columns
    "table.time": "Time",
    "table.provider": "Provider",
    "table.model": "Model",
    "table.input": "Input",
    "table.output": "Output",
    "table.total": "Total",
    "table.cost": "Cost",
    "table.latency": "Latency",

    # Export
    "export.csv_title": "Export CSV",
    "export.csv_file": "token_history.csv",
    "export.csv_filter": "CSV Files (*.csv)",
    "export.excel_title": "Export Excel",
    "export.excel_file": "token_history.xlsx",
    "export.excel_filter": "Excel Files (*.xlsx)",
    "export.complete": "Export Complete",
    "export.msg": "Data exported to {path}",
    "export.failed": "Export Failed",

    # Budget alerts
    "budget.alert_title": "Budget Alert",
    "budget.alert_80": "80% of {type} budget used",
    "budget.alert_90": "90% of {type} budget used",
    "budget.alert_100": "{type} budget exceeded!",
}

# Cache for dynamic translations (model names, providers, etc. stay as-is)
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": _EN,
    "zh_CN": _ZH,
}

_current_lang = "en"


# ── Public API ──────────────────────────────────────────────────

def set_language(lang: str) -> None:
    """Set the active language.

    Args:
        lang: Language code — 'en' or 'zh_CN'.
    """
    global _current_lang
    if lang in _TRANSLATIONS:
        _current_lang = lang
        logger.info("Language set to %s", lang)
    else:
        logger.warning("Unknown language: %s, falling back to en", lang)
        _current_lang = "en"


def get_language() -> str:
    """Get the current language code."""
    return _current_lang


def tr(key: str, **kwargs: Any) -> str:
    """Translate a key to the current language.

    Args:
        key: Translation key (e.g., 'main.title').
        **kwargs: Format arguments for the translation string.

    Returns:
        Translated string, or the key itself if not found.

    Usage:
        tr('main.title')
        tr('main.in_out', input='2.5M', output='1.2M')
    """
    table = _TRANSLATIONS.get(_current_lang, _EN)
    text = table.get(key)
    if text is None:
        # Fallback to English
        text = _EN.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text


def tr_en(key: str) -> str:
    """Get the English translation for a key (used for fallback/size)."""
    return _EN.get(key, key)
