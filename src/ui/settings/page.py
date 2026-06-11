"""
Settings page — application configuration.

Covers: startup, proxy, display, data management, language switching.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.config import AppConfig, ConfigManager
from src.database.repository import Repository
from src.utils.i18n import tr, set_language, get_language


class SettingsPage(QWidget):
    """Application settings page."""

    def __init__(
        self,
        config: AppConfig,
        config_manager: ConfigManager,
        repository: Repository,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._config_manager = config_manager
        self._repo = repository
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        main = QWidget()
        scroll.setWidget(main)

        layout = QVBoxLayout(main)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(24)

        self._title = QLabel(tr("settings.title"))
        self._title.setStyleSheet("font-size: 28px; font-weight: 700;")
        layout.addWidget(self._title)

        # General
        self._general_group = QGroupBox(tr("settings.general"))
        gen_layout = QVBoxLayout(self._general_group)
        gen_layout.setSpacing(14)

        self._startup_check = QCheckBox(tr("settings.startup_auto"))
        gen_layout.addWidget(self._startup_check)
        self._tray_check = QCheckBox(tr("settings.close_to_tray"))
        gen_layout.addWidget(self._tray_check)
        self._floating_check = QCheckBox(tr("settings.show_floating"))
        gen_layout.addWidget(self._floating_check)

        layout.addWidget(self._general_group)

        # Proxy
        proxy_group = QGroupBox(tr("settings.proxy"))
        proxy_form = QFormLayout(proxy_group)
        proxy_form.setSpacing(14)

        self._proxy_host = QLineEdit()
        self._proxy_host.setPlaceholderText("127.0.0.1")
        proxy_form.addRow(tr("settings.proxy_host"), self._proxy_host)

        self._proxy_port = QSpinBox()
        self._proxy_port.setRange(1024, 65535)
        proxy_form.addRow(tr("settings.proxy_port"), self._proxy_port)

        layout.addWidget(proxy_group)

        # Data
        data_group = QGroupBox(tr("settings.data"))
        data_form = QFormLayout(data_group)
        data_form.setSpacing(14)

        self._db_path = QLineEdit()
        self._db_path.setReadOnly(True)
        data_form.addRow(tr("settings.db_path"), self._db_path)

        clear_btn = QPushButton(tr("settings.clear_data"))
        clear_btn.setProperty("danger", True)
        clear_btn.clicked.connect(self._confirm_clear_data)
        data_form.addRow("", clear_btn)

        layout.addWidget(data_group)

        # Display
        display_group = QGroupBox(tr("settings.display"))
        display_form = QFormLayout(display_group)
        display_form.setSpacing(14)

        self._theme_combo = QLineEdit()
        self._theme_combo.setText("dark")
        self._theme_combo.setReadOnly(True)
        display_form.addRow(tr("settings.theme"), self._theme_combo)

        # Language selector
        self._lang_combo = QComboBox()
        self._lang_combo.addItems([tr("settings.lang_en"), tr("settings.lang_zh")])
        current_lang = get_language()
        self._lang_combo.setCurrentIndex(0 if current_lang == "en" else 1)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        display_form.addRow(tr("settings.language"), self._lang_combo)

        self._float_width = QSpinBox()
        self._float_width.setRange(180, 500)
        self._float_width.setValue(260)
        display_form.addRow(tr("settings.float_width"), self._float_width)

        self._float_height = QSpinBox()
        self._float_height.setRange(60, 250)
        self._float_height.setValue(80)
        display_form.addRow(tr("settings.float_height"), self._float_height)

        layout.addWidget(display_group)

        # Save
        save_btn = QPushButton(tr("settings.save"))
        save_btn.setProperty("accent", True)
        save_btn.clicked.connect(self._save_settings)
        save_btn.setMinimumHeight(48)
        layout.addWidget(save_btn)

        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _on_language_changed(self, index: int) -> None:
        """Handle language combo box change and immediately switch language."""
        new_lang = "en" if index == 0 else "zh_CN"
        set_language(new_lang)
        self._repo.set_setting("language", new_lang)
        self.refresh_language()
        # Propagate to main window
        win = self.window()
        if hasattr(win, "refresh_language"):
            win.refresh_language()

    def refresh_language(self) -> None:
        """Refresh all displayed text after language change."""
        self._title.setText(tr("settings.title"))
        self._general_group.setTitle(tr("settings.general"))
        self._startup_check.setText(tr("settings.startup_auto"))
        self._tray_check.setText(tr("settings.close_to_tray"))
        self._floating_check.setText(tr("settings.show_floating"))

        # Rebuild language combo without triggering signal
        self._lang_combo.blockSignals(True)
        current = 0 if get_language() == "en" else 1
        self._lang_combo.clear()
        self._lang_combo.addItems([tr("settings.lang_en"), tr("settings.lang_zh")])
        self._lang_combo.setCurrentIndex(current)
        self._lang_combo.blockSignals(False)

        # Update group titles
        for group, key in [
            (self._general_group, "settings.general"),
        ]:
            group.setTitle(tr(key))

        # Find proxy, data, display groups and update them
        for child in self.findChildren(QGroupBox):
            title = child.title()
            if "Proxy" in title or "代理" in title or "Server" in title:
                child.setTitle(tr("settings.proxy"))
            elif "Data" in title or "数据" in title:
                child.setTitle(tr("settings.data"))
            elif "Display" in title or "显示" in title:
                child.setTitle(tr("settings.display"))

        # Update form labels
        for child in self.findChildren(QPushButton):
            text = child.text()
            if "Save" in text or "保存" in text:
                child.setText(tr("settings.save"))
            elif "Clear" in text or "清除" in text:
                child.setText(tr("settings.clear_data"))

    def _load_settings(self) -> None:
        self._startup_check.setChecked(self._config.startup_auto_run)
        self._tray_check.setChecked(self._config.close_to_tray)
        self._floating_check.setChecked(self._config.floating_enabled)
        self._proxy_host.setText(self._config.proxy_host)
        self._proxy_port.setValue(self._config.proxy_port)
        self._db_path.setText(self._config.db_path)
        self._float_width.setValue(self._config.floating_width)
        self._float_height.setValue(self._config.floating_height)

    def _save_settings(self) -> None:
        self._config.startup_auto_run = self._startup_check.isChecked()
        self._config.close_to_tray = self._tray_check.isChecked()
        self._config.floating_enabled = self._floating_check.isChecked()
        self._config.proxy_host = self._proxy_host.text().strip()
        self._config.proxy_port = self._proxy_port.value()
        self._config.floating_width = self._float_width.value()
        self._config.floating_height = self._float_height.value()

        self._config_manager.save_yaml()

        self._repo.set_setting("startup_auto_run", "1" if self._config.startup_auto_run else "0")
        self._repo.set_setting("close_to_tray", "1" if self._config.close_to_tray else "0")
        self._repo.set_setting("show_floating", "1" if self._config.floating_enabled else "0")
        self._repo.set_setting("proxy_host", self._config.proxy_host)
        self._repo.set_setting("proxy_port", str(self._config.proxy_port))

        QMessageBox.information(self, tr("settings.saved"), tr("settings.saved_msg"))

    def _confirm_clear_data(self) -> None:
        reply = QMessageBox.warning(
            self,
            tr("settings.clear_confirm_title"),
            tr("settings.clear_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._repo._db.execute("DELETE FROM request_logs")
            self._repo._db.execute("DELETE FROM daily_stats")
            self._repo._db.commit()
            QMessageBox.information(self, tr("settings.cleared"), tr("settings.cleared_msg"))
