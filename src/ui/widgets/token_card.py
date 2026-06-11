"""
Token stat card widget — displays a single metric in a styled card.

Used on the Main page for key metrics like:
- Today's Tokens
- Today's Cost
- Active Models
- Request Count
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class TokenCard(QFrame):
    """A styled metric card for the main page.

    Usage:
        card = TokenCard("Today Tokens", "2.41M", "↑ 12% vs yesterday")
    """

    def __init__(
        self,
        title: str,
        value: str = "—",
        subtitle: str = "",
        accent_color: str = "#58a6ff",
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the token card.

        Args:
            title: Card title (e.g., "Today Tokens").
            value: Main value display (e.g., "2.41M").
            subtitle: Secondary text below value.
            accent_color: Color for the left border accent.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._title = title
        self._accent_color = accent_color

        self.setObjectName("tokenCard")
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.setMinimumHeight(120)
        self.setStyleSheet(f"""
            TokenCard {{
                background-color: #1c2128;
                border: 1px solid #30363d;
                border-left: 3px solid {accent_color};
                border-radius: 8px;
                padding: 14px 18px;
            }}
            TokenCard:hover {{
                background-color: #21262d;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        # Title
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet("color: #8b949e; font-size: 16px; font-weight: 500;")
        layout.addWidget(self._title_label)

        # Value
        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(
            "color: #e6edf3; font-size: 28px; font-weight: 700;"
            "font-family: 'Cascadia Code', 'Consolas', 'Fira Code', monospace;"
        )
        layout.addWidget(self._value_label)

        # Subtitle
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setStyleSheet("color: #8b949e; font-size: 15px;")
        layout.addWidget(self._subtitle_label)

    def set_value(self, value: str) -> None:
        """Update the main value display.

        Args:
            value: New value string.
        """
        self._value_label.setText(value)

    def set_subtitle(self, text: str) -> None:
        """Update the subtitle text.

        Args:
            text: New subtitle string.
        """
        self._subtitle_label.setText(text)


def format_token_count(count: int) -> str:
    """Format a token count for human-readable display.

    Args:
        count: Raw token count.

    Returns:
        Formatted string like '2.41M', '523K', '1.2B'.
    """
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.2f}B"
    elif count >= 1_000_000:
        return f"{count / 1_000_000:.2f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    else:
        return str(count)


def format_cost(amount: float) -> str:
    """Format a cost value for display.

    Args:
        amount: Cost in dollars.

    Returns:
        Formatted string like '$4.52'.
    """
    if amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"
