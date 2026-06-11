"""
Budget management page — set budget limits and track spending.

Supports daily, weekly, and monthly budgets with threshold notifications.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.database.repository import Repository
from src.statistics.engine import StatisticsEngine
from src.utils.i18n import tr


class BudgetPage(QWidget):
    """Budget configuration and tracking page."""

    def __init__(
        self,
        repository: Repository,
        engine: StatisticsEngine,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repository
        self._engine = engine
        self._setup_ui()
        self._load_budgets()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        main = QWidget()
        scroll.setWidget(main)

        layout = QVBoxLayout(main)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(24)

        self._title = QLabel(tr("budget.title"))
        self._title.setStyleSheet("font-size: 28px; font-weight: 700;")
        layout.addWidget(self._title)

        self._daily_group = self._create_budget_group(tr("budget.daily"), "daily")
        layout.addWidget(self._daily_group)
        self._weekly_group = self._create_budget_group(tr("budget.weekly"), "weekly")
        layout.addWidget(self._weekly_group)
        self._monthly_group = self._create_budget_group(tr("budget.monthly"), "monthly")
        layout.addWidget(self._monthly_group)

        save_btn = QPushButton(tr("budget.save_all"))
        save_btn.setProperty("accent", True)
        save_btn.clicked.connect(self._save_all)
        save_btn.setMinimumHeight(48)
        layout.addWidget(save_btn)

        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _create_budget_group(self, title: str, budget_type: str) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setSpacing(14)

        amount_layout = QHBoxLayout()
        amount_layout.addWidget(QLabel(tr("budget.amount")))

        spin = QDoubleSpinBox()
        spin.setRange(0, 100000)
        spin.setDecimals(2)
        spin.setPrefix("$")
        spin.setFixedWidth(200)
        spin.setObjectName(f"spin_{budget_type}")
        amount_layout.addWidget(spin)
        amount_layout.addStretch()
        layout.addLayout(amount_layout)

        notify_layout = QHBoxLayout()
        notify_layout.addWidget(QLabel(tr("budget.notify_at")))

        cb_80 = QCheckBox(tr("budget.pct_80"))
        cb_80.setObjectName(f"cb80_{budget_type}")
        cb_80.setChecked(True)
        notify_layout.addWidget(cb_80)
        cb_90 = QCheckBox(tr("budget.pct_90"))
        cb_90.setObjectName(f"cb90_{budget_type}")
        cb_90.setChecked(True)
        notify_layout.addWidget(cb_90)
        cb_100 = QCheckBox(tr("budget.pct_100"))
        cb_100.setObjectName(f"cb100_{budget_type}")
        cb_100.setChecked(True)
        notify_layout.addWidget(cb_100)
        notify_layout.addStretch()
        layout.addLayout(notify_layout)

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel(tr("budget.current")))

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setObjectName(f"progress_{budget_type}")
        progress_layout.addWidget(progress)

        spent_label = QLabel("$0.00 / —")
        spent_label.setObjectName(f"spent_{budget_type}")
        progress_layout.addWidget(spent_label)
        layout.addLayout(progress_layout)

        return group

    def _load_budgets(self) -> None:
        for budget_type in ("daily", "weekly", "monthly"):
            budget = self._repo.get_budget(budget_type)
            status = self._engine.get_budget_status(budget_type)

            spin = self.findChild(QDoubleSpinBox, f"spin_{budget_type}")
            if spin and budget:
                spin.setValue(budget.get("amount", 0.0))

            if budget:
                for pct in (80, 90, 100):
                    cb = self.findChild(QCheckBox, f"cb{pct}_{budget_type}")
                    if cb:
                        cb.setChecked(bool(budget.get(f"notify_{pct}", 1)))

            progress = self.findChild(QProgressBar, f"progress_{budget_type}")
            spent_label = self.findChild(QLabel, f"spent_{budget_type}")

            if progress and status.get("configured"):
                pct = min(100, int(status["percentage"]))
                progress.setValue(pct)
                if pct >= 100:
                    progress.setStyleSheet("QProgressBar::chunk { background-color: #f85149; }")
                elif pct >= 80:
                    progress.setStyleSheet("QProgressBar::chunk { background-color: #d2991d; }")
                else:
                    progress.setStyleSheet("QProgressBar::chunk { background-color: #3fb950; }")

                if spent_label:
                    spent_label.setText(
                        f"${status['spent']:.2f} / ${status['amount']:.2f} "
                        f"({status['percentage']:.1f}%)"
                    )

    def _save_all(self) -> None:
        for budget_type in ("daily", "weekly", "monthly"):
            spin = self.findChild(QDoubleSpinBox, f"spin_{budget_type}")
            if spin is None:
                continue
            amount = spin.value()
            if amount > 0:
                self._repo.set_budget(budget_type, amount)
        self._load_budgets()
