"""
Models management page — CRUD for model pricing configurations.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from src.database.repository import Repository
from src.statistics.calculator import CostCalculator
from src.utils.i18n import tr


class ModelsPage(QWidget):
    """Model configuration management page."""

    def __init__(
        self,
        repository: Repository,
        calculator: CostCalculator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repository
        self._calculator = calculator
        self._setup_ui()
        self._load_models()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        header = QHBoxLayout()
        self._title = QLabel(tr("models.title"))
        self._title.setStyleSheet("font-size: 28px; font-weight: 700;")
        header.addWidget(self._title)
        header.addStretch()

        self._add_btn = QPushButton(tr("models.add"))
        self._add_btn.setProperty("accent", True)
        self._add_btn.clicked.connect(self._add_model)
        header.addWidget(self._add_btn)

        self._refresh_btn = QPushButton(tr("models.refresh"))
        self._refresh_btn.clicked.connect(self._refresh_prices)
        header.addWidget(self._refresh_btn)

        layout.addLayout(header)

        self._table = QTableWidget()
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels([
            tr("models.provider"), tr("models.model_name"),
            tr("models.display_name"), tr("models.api_url"),
            tr("models.input_price"), tr("models.output_price"),
            tr("models.currency"), tr("models.enabled"), "",
        ])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)

        hv = self._table.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hv.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hv.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(8, 180)

        layout.addWidget(self._table)

    def _load_models(self) -> None:
        models = self._repo.get_all_models()
        self._table.setRowCount(len(models))

        enabled_text = tr("models.yes")
        disabled_text = tr("models.no")

        for row, model in enumerate(models):
            self._table.setItem(row, 0, QTableWidgetItem(model.get("provider", "")))
            self._table.setItem(row, 1, QTableWidgetItem(model.get("model_name", "")))
            self._table.setItem(row, 2, QTableWidgetItem(model.get("display_name", "")))
            self._table.setItem(row, 3, QTableWidgetItem(model.get("api_url", "")))
            self._table.setItem(row, 4, QTableWidgetItem(f"${model.get('input_price', 0):.2f}"))
            self._table.setItem(row, 5, QTableWidgetItem(f"${model.get('output_price', 0):.2f}"))
            self._table.setItem(row, 6, QTableWidgetItem(model.get("currency", "USD")))
            self._table.setItem(row, 7, QTableWidgetItem(
                enabled_text if model.get("enabled") else disabled_text
            ))

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(4)

            edit_btn = QPushButton(tr("models.edit"))
            edit_btn.clicked.connect(lambda checked, m=model: self._edit_model(m))
            action_layout.addWidget(edit_btn)

            del_btn = QPushButton(tr("models.delete"))
            del_btn.setProperty("danger", True)
            del_btn.clicked.connect(lambda checked, m=model: self._delete_model(m))
            action_layout.addWidget(del_btn)

            self._table.setCellWidget(row, 8, action_widget)

    def _add_model(self) -> None:
        dialog = ModelEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self._repo.insert_model(data)
            self._refresh_prices()
            self._load_models()

    def _edit_model(self, model: dict[str, Any]) -> None:
        dialog = ModelEditDialog(self, model)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self._repo.update_model(model["id"], data)
            self._refresh_prices()
            self._load_models()

    def _delete_model(self, model: dict[str, Any]) -> None:
        name = model.get('display_name', model.get('model_name'))
        reply = QMessageBox.question(
            self,
            tr("models.delete_title"),
            tr("models.delete_confirm", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._repo.delete_model(model["id"])
            self._refresh_prices()
            self._load_models()

    def _refresh_prices(self) -> None:
        self._calculator.refresh()


class ModelEditDialog(QDialog):
    """Dialog for adding/editing a model configuration."""

    def __init__(
        self,
        parent: QWidget | None = None,
        model: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self.setWindowTitle(
            tr("models.dialog_title_edit") if model else tr("models.dialog_title_add")
        )
        self.setMinimumWidth(520)

        layout = QFormLayout(self)
        layout.setSpacing(14)

        self._provider = QLineEdit()
        self._provider.setPlaceholderText("e.g., openai, anthropic")
        if model:
            self._provider.setText(model.get("provider", ""))
        layout.addRow(tr("models.dialog_provider"), self._provider)

        self._model_name = QLineEdit()
        self._model_name.setPlaceholderText("e.g., gpt-4o")
        if model:
            self._model_name.setText(model.get("model_name", ""))
        layout.addRow(tr("models.dialog_model_name"), self._model_name)

        self._display_name = QLineEdit()
        self._display_name.setPlaceholderText("e.g., GPT-4o")
        if model:
            self._display_name.setText(model.get("display_name", ""))
        layout.addRow(tr("models.dialog_display_name"), self._display_name)

        self._api_url = QLineEdit()
        self._api_url.setPlaceholderText("e.g., https://api.openai.com/v1")
        if model:
            self._api_url.setText(model.get("api_url", ""))
        layout.addRow(tr("models.dialog_api_url"), self._api_url)

        self._input_price = QDoubleSpinBox()
        self._input_price.setRange(0, 10000)
        self._input_price.setDecimals(4)
        self._input_price.setPrefix("$")
        self._input_price.setSuffix(" / 1M tokens")
        if model:
            self._input_price.setValue(model.get("input_price", 0.0))
        layout.addRow(tr("models.dialog_input_price"), self._input_price)

        self._output_price = QDoubleSpinBox()
        self._output_price.setRange(0, 10000)
        self._output_price.setDecimals(4)
        self._output_price.setPrefix("$")
        self._output_price.setSuffix(" / 1M tokens")
        if model:
            self._output_price.setValue(model.get("output_price", 0.0))
        layout.addRow(tr("models.dialog_output_price"), self._output_price)

        self._enabled = QCheckBox()
        self._enabled.setChecked(model.get("enabled", 1) == 1 if model else True)
        layout.addRow(tr("models.dialog_enabled"), self._enabled)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate_and_accept(self) -> None:
        if not self._provider.text().strip():
            QMessageBox.warning(self, tr("models.validation_title"),
                              tr("models.validation_provider"))
            return
        if not self._model_name.text().strip():
            QMessageBox.warning(self, tr("models.validation_title"),
                              tr("models.validation_model"))
            return
        self.accept()

    def get_data(self) -> dict[str, Any]:
        return {
            "provider": self._provider.text().strip(),
            "model_name": self._model_name.text().strip(),
            "display_name": self._display_name.text().strip(),
            "api_url": self._api_url.text().strip(),
            "input_price": self._input_price.value(),
            "output_price": self._output_price.value(),
            "enabled": 1 if self._enabled.isChecked() else 0,
        }
