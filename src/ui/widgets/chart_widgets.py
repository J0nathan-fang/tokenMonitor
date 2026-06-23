"""
Chart wrapper widgets using PyQtGraph.

Provides abstraction for line charts, bar charts, and pie charts
used on Dashboard and History pages.
"""

from __future__ import annotations

from typing import Any

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget

# Configure PyQtGraph for dark theme
pg.setConfigOption("background", "#0d1117")
pg.setConfigOption("foreground", "#e6edf3")
pg.setConfigOptions(antialias=True)


class LineChartWidget(QWidget):
    """Line chart for displaying time-series token/cost data."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        """Initialize the line chart.

        Args:
            title: Chart title.
            parent: Parent widget.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", title)
        self._plot.setLabel("bottom", "Date")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.getPlotItem().getAxis("left").setPen("#8b949e")
        self._plot.getPlotItem().getAxis("bottom").setPen("#8b949e")

        layout.addWidget(self._plot)

    def plot(self, x: list, y: list, label: str = "", color: str = "#58a6ff") -> None:
        """Plot data on the chart.

        Args:
            x: X-axis values (dates as strings).
            y: Y-axis values (token counts or costs).
            label: Legend label.
            color: Line color.
        """
        self._plot.clear()
        pen = pg.mkPen(color=color, width=2)
        # Convert string x to numeric indices for PyQtGraph
        x_indices = list(range(len(x)))
        self._plot.plot(x_indices, y, pen=pen, name=label)

        # Set x-axis tick labels
        if x:
            ticks = []
            step = max(1, len(x) // 7)
            for i in range(0, len(x), step):
                ticks.append((i, x[i]))
            self._plot.getPlotItem().getAxis("bottom").setTicks([ticks])


class BarChartWidget(QWidget):
    """Bar chart for comparing token/cost across models or days."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        """Initialize the bar chart.

        Args:
            title: Chart title.
            parent: Parent widget.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", title)
        self._plot.showGrid(x=False, y=True, alpha=0.3)
        self._plot.getPlotItem().getAxis("left").setPen("#8b949e")
        self._plot.getPlotItem().getAxis("bottom").setPen("#8b949e")

        layout.addWidget(self._plot)

    def plot(self, labels: list[str], values: list[float], color: str = "#58a6ff") -> None:
        """Plot bar chart data.

        Args:
            labels: Bar labels.
            values: Bar values.
            color: Bar color.
        """
        self._plot.clear()
        x = list(range(len(labels)))
        bar = pg.BarGraphItem(x=x, height=values, width=0.6, brush=color)
        self._plot.addItem(bar)

        # Set x-axis labels
        ticks = [(i, label) for i, label in enumerate(labels)]
        self._plot.getPlotItem().getAxis("bottom").setTicks([ticks])


class PieChartWidget(QWidget):
    """Pie/donut chart for model distribution.

    Uses PyQtGraph (which doesn't have native pie charts, so we draw via PlotItem).
    """

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        """Initialize the pie chart widget.

        Args:
            title: Chart title.
            parent: Parent widget.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", title)
        self._plot.hideAxis("left")
        self._plot.showGrid(False, False)
        self._plot.setAspectLocked(True)

        layout.addWidget(self._plot)

    def plot(self, labels: list[str], values: list[float]) -> None:
        """Plot model distribution as a pie-like scatter chart.

        Since PyQtGraph doesn't have native pie charts, we use
        a scatter plot with sized points as a simplified representation.

        For a production app, consider using QtWebEngine + ECharts.

        Args:
            labels: Slice labels.
            values: Slice values.
        """
        self._plot.clear()
        colors = ["#58a6ff", "#3fb950", "#d2991d", "#f85149", "#a371f7", "#39c5cf"]

        total = sum(values)
        if total == 0:
            return

        # Create a scatter plot where each point represents a model
        # with size proportional to its share
        for i, (label, value) in enumerate(zip(labels, values)):
            pct = (value / total) * 100
            color = colors[i % len(colors)]
            scatter = pg.ScatterPlotItem(
                [i * 1.5],
                [0],
                size=max(20, pct * 3),
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color="white", width=1),
                name=f"{label} ({pct:.1f}%)",
            )
            self._plot.addItem(scatter)

        self._plot.setXRange(-1, len(labels) * 1.5)
        self._plot.setYRange(-2, 2)

        # Add legend
        if labels:
            self._plot.addLegend(offset=(10, 10))


class ModelDistributionChart(QWidget):
    """Horizontal bar chart for model token distribution.

    Y-axis: model IDs (top → bottom = highest → lowest token count).
    X-axis: token consumption as horizontal bar length.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the distribution chart.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "Tokens")
        self._plot.showGrid(x=True, y=False, alpha=0.3)
        self._plot.getPlotItem().getAxis("left").setPen("#8b949e")
        self._plot.getPlotItem().getAxis("bottom").setPen("#8b949e")

        layout.addWidget(self._plot)

    def plot(self, labels: list[str], values: list[float]) -> None:
        """Plot horizontal bars — model names on Y, token counts on X.

        Bars are sorted so the model with the most tokens appears at
        the top of the Y axis.

        Args:
            labels: Model names (already sorted desc by token count).
            values: Token counts (same order as labels).
        """
        self._plot.clear()

        if not labels or not values:
            return

        colors = ["#58a6ff", "#3fb950", "#d2991d", "#f85149", "#a371f7", "#39c5cf"]

        # Y positions: 0 = top bar, N-1 = bottom bar
        y = list(range(len(labels)))

        # Horizontal bars — width extends right by token count, height is bar thickness
        bar = pg.BarGraphItem(
            x0=[0] * len(values),
            y=y,
            width=values,
            height=0.6,
            brushes=[colors[i % len(colors)] for i in range(len(labels))],
        )
        self._plot.addItem(bar)

        # Y-axis: model names, highest-token model at top
        ticks = [(i, label) for i, label in enumerate(labels)]
        self._plot.getPlotItem().getAxis("left").setTicks([ticks])
        self._plot.getPlotItem().invertY(True)

        # Fit all bars in view
        self._plot.setYRange(-0.8, len(labels) - 0.2)
