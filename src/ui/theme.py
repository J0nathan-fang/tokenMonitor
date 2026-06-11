"""
Dark theme manager for TokenMonitor.

Style inspired by Cursor, Claude Desktop, and Cherry Studio.
Font sizes scaled up for readability (base 17px).
"""

from __future__ import annotations

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.utils.i18n import get_language

# Color palette
COLORS = {
    # Backgrounds
    "bg_primary": "#0d1117",
    "bg_secondary": "#161b22",
    "bg_tertiary": "#21262d",
    "bg_card": "#1c2128",
    "bg_hover": "#292e36",
    "bg_input": "#0d1117",

    # Borders
    "border_primary": "#30363d",
    "border_secondary": "#21262d",

    # Text
    "text_primary": "#e6edf3",
    "text_secondary": "#8b949e",
    "text_muted": "#484f58",
    "text_link": "#58a6ff",

    # Accent
    "accent_blue": "#58a6ff",
    "accent_green": "#3fb950",
    "accent_orange": "#d2991d",
    "accent_red": "#f85149",
    "accent_purple": "#a371f7",
    "accent_cyan": "#39c5cf",

    # Widget-specific
    "scrollbar_bg": "#161b22",
    "scrollbar_handle": "#484f58",
    "scrollbar_handle_hover": "#6e7681",

    "tab_active": "#1c2128",
    "tab_inactive": "#0d1117",

    "progress_bg": "#21262d",
    "progress_fill": "#3fb950",

    "table_header": "#161b22",
    "table_row_alt": "#161b22",
    "table_row": "#0d1117",
    "table_row_hover": "#1c2128",
}


def get_font_family() -> str:
    """Get the font family string for the current language.

    Uses Microsoft YaHei for Chinese, Segoe UI for English.
    """
    lang = get_language()
    if lang == "zh_CN":
        return '"Microsoft YaHei", "Segoe UI", "Noto Sans SC", sans-serif'
    return '"Segoe UI", "Microsoft YaHei", sans-serif'


def get_stylesheet() -> str:
    """Get the complete application stylesheet.

    Font sizes have been increased by 4-8px from the original
    for better readability on modern displays.

    Returns:
        QSS stylesheet string.
    """
    c = COLORS
    font = get_font_family()
    return f"""
    /* ── Global ─────────────────────────────────── */
    QWidget {{
        background-color: {c["bg_primary"]};
        color: {c["text_primary"]};
        font-family: {font};
        font-size: 17px;
    }}

    /* ── Main Window ────────────────────────────── */
    QMainWindow {{
        background-color: {c["bg_primary"]};
    }}

    /* ── Sidebar ────────────────────────────────── */
    QListWidget {{
        background-color: {c["bg_secondary"]};
        border: none;
        outline: none;
        padding: 8px 4px;
        font-size: 30px;
    }}
    QListWidget::item {{
        padding: 12px 16px;
        border-radius: 8px;
        margin: 2px 4px;
        color: #ffffff;
    }}
    QListWidget::item:selected {{
        background-color: {c["bg_tertiary"]};
        color: {c["text_primary"]};
        font-weight: 600;
    }}
    QListWidget::item:hover:!selected {{
        background-color: {c["bg_hover"]};
        color: {c["text_primary"]};
    }}

    /* ── Buttons ────────────────────────────────── */
    QPushButton {{
        background-color: {c["bg_tertiary"]};
        border: 1px solid {c["border_primary"]};
        border-radius: 6px;
        padding: 10px 20px;
        color: {c["text_primary"]};
        font-size: 17px;
    }}
    QPushButton:hover {{
        background-color: {c["bg_hover"]};
        border-color: {c["text_muted"]};
    }}
    QPushButton:pressed {{
        background-color: {c["bg_secondary"]};
    }}
    QPushButton:disabled {{
        color: {c["text_muted"]};
        border-color: {c["border_secondary"]};
    }}
    QPushButton[accent="true"] {{
        background-color: {c["accent_blue"]};
        border: none;
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{
        background-color: #4090e0;
    }}
    QPushButton[danger="true"] {{
        background-color: transparent;
        border: 1px solid {c["accent_red"]};
        color: {c["accent_red"]};
    }}
    QPushButton[danger="true"]:hover {{
        background-color: rgba(248, 81, 73, 0.15);
    }}

    /* ── Input Fields ──────────────────────────── */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {c["bg_input"]};
        border: 1px solid {c["border_primary"]};
        border-radius: 6px;
        padding: 10px 14px;
        color: {c["text_primary"]};
        font-size: 17px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {c["accent_blue"]};
    }}
    QComboBox::drop-down {{
        border: none;
        padding-right: 8px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c["bg_tertiary"]};
        border: 1px solid {c["border_primary"]};
        selection-background-color: {c["bg_hover"]};
        color: {c["text_primary"]};
        font-size: 17px;
    }}

    /* ── Labels ─────────────────────────────────── */
    QLabel {{
        color: {c["text_primary"]};
        background: transparent;
    }}
    QLabel[secondary="true"] {{
        color: {c["text_secondary"]};
        font-size: 16px;
    }}
    QLabel[heading="true"] {{
        font-size: 24px;
        font-weight: 700;
    }}
    QLabel[subheading="true"] {{
        font-size: 18px;
        font-weight: 600;
        color: {c["text_secondary"]};
    }}
    QLabel[value="true"] {{
        font-size: 28px;
        font-weight: 700;
        font-family: "Cascadia Code", "Consolas", "Fira Code", monospace;
    }}

    /* ── Tables ─────────────────────────────────── */
    QTableWidget {{
        background-color: {c["bg_primary"]};
        border: 1px solid {c["border_primary"]};
        border-radius: 8px;
        gridline-color: {c["border_secondary"]};
        selection-background-color: {c["bg_hover"]};
        font-size: 17px;
    }}
    QTableWidget::item {{
        padding: 10px 14px;
        border-bottom: 1px solid {c["border_secondary"]};
    }}
    QTableWidget::item:selected {{
        background-color: {c["bg_hover"]};
        color: {c["text_primary"]};
    }}
    QHeaderView::section {{
        background-color: {c["table_header"]};
        color: {c["text_secondary"]};
        padding: 12px 14px;
        border: none;
        border-bottom: 1px solid {c["border_primary"]};
        font-weight: 600;
        font-size: 16px;
        text-transform: uppercase;
    }}

    /* ── Scrollbars ─────────────────────────────── */
    QScrollBar:vertical {{
        background: {c["scrollbar_bg"]};
        width: 10px;
        margin: 0;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {c["scrollbar_handle"]};
        min-height: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c["scrollbar_handle_hover"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {c["scrollbar_bg"]};
        height: 10px;
        margin: 0;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c["scrollbar_handle"]};
        min-width: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c["scrollbar_handle_hover"]};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* ── Progress Bars ──────────────────────────── */
    QProgressBar {{
        background-color: {c["progress_bg"]};
        border: none;
        border-radius: 4px;
        height: 10px;
        text-align: center;
        font-size: 14px;
    }}
    QProgressBar::chunk {{
        background-color: {c["progress_fill"]};
        border-radius: 4px;
    }}

    /* ── Tabs ───────────────────────────────────── */
    QTabWidget::pane {{
        border: 1px solid {c["border_primary"]};
        border-radius: 8px;
        background: {c["bg_primary"]};
    }}
    QTabBar::tab {{
        padding: 12px 24px;
        margin-right: 2px;
        color: {c["text_secondary"]};
        border-bottom: 2px solid transparent;
        font-size: 17px;
    }}
    QTabBar::tab:selected {{
        color: {c["text_primary"]};
        border-bottom: 2px solid {c["accent_blue"]};
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{
        color: {c["text_primary"]};
    }}

    /* ── Tool Tips ──────────────────────────────── */
    QToolTip {{
        background-color: {c["bg_tertiary"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border_primary"]};
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 16px;
    }}

    /* ── Checkboxes & Radio ─────────────────────── */
    QCheckBox, QRadioButton {{
        color: {c["text_primary"]};
        spacing: 8px;
        font-size: 17px;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 20px;
        height: 20px;
        border: 1px solid {c["border_primary"]};
        border-radius: 4px;
        background-color: {c["bg_input"]};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {c["accent_blue"]};
        border-color: {c["accent_blue"]};
    }}

    /* ── Group Box ──────────────────────────────── */
    QGroupBox {{
        border: 1px solid {c["border_primary"]};
        border-radius: 8px;
        margin-top: 20px;
        padding-top: 24px;
        font-weight: 600;
        font-size: 17px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 16px;
        padding: 0 8px;
        color: {c["text_primary"]};
    }}

    /* ── Date Edit ──────────────────────────────── */
    QDateEdit {{
        background-color: {c["bg_input"]};
        border: 1px solid {c["border_primary"]};
        border-radius: 6px;
        padding: 10px 14px;
        color: {c["text_primary"]};
        font-size: 17px;
    }}
    QDateEdit:focus {{
        border-color: {c["accent_blue"]};
    }}
    QDateEdit::drop-down {{
        border: none;
    }}

    /* ── Splitter ───────────────────────────────── */
    QSplitter::handle {{
        background-color: {c["border_primary"]};
    }}
    QSplitter::handle:horizontal {{
        width: 1px;
    }}
    QSplitter::handle:vertical {{
        height: 1px;
    }}

    /* ── Menu ───────────────────────────────────── */
    QMenu {{
        background-color: {c["bg_tertiary"]};
        border: 1px solid {c["border_primary"]};
        border-radius: 8px;
        padding: 4px;
        color: {c["text_primary"]};
        font-size: 17px;
    }}
    QMenu::item {{
        padding: 10px 36px 10px 20px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {c["bg_hover"]};
    }}
    QMenu::separator {{
        height: 1px;
        background: {c["border_primary"]};
        margin: 4px 8px;
    }}
    """


def apply_theme(app: QApplication) -> None:
    """Apply the dark theme to the entire application.

    Args:
        app: The QApplication instance.
    """
    app.setStyle("Fusion")

    # Set up dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg_primary"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["bg_input"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["bg_secondary"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["bg_tertiary"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["bg_tertiary"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(COLORS["accent_red"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(COLORS["accent_blue"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["accent_blue"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS["text_muted"]))
    app.setPalette(palette)

    # Apply stylesheet
    app.setStyleSheet(get_stylesheet())
