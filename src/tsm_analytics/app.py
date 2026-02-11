from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QDate, QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .csv_processing import (
    ColumnMapping,
    autodetect_mapping,
    daily_aggregates,
    extract_headers,
    has_required_mapping,
    normalize_sales_data,
)
from .table_model import DataFrameTableModel


@dataclass
class WorkerResult:
    frame: pd.DataFrame
    error: str = ""


class LoaderWorker(QObject):
    finished = Signal(object)

    def __init__(self, csv_path: str, mapping: ColumnMapping) -> None:
        super().__init__()
        self.csv_path = csv_path
        self.mapping = mapping

    def run(self) -> None:
        try:
            frame = normalize_sales_data(self.csv_path, self.mapping)
            self.finished.emit(WorkerResult(frame=frame))
        except Exception as exc:  # pylint: disable=broad-except
            self.finished.emit(WorkerResult(frame=pd.DataFrame(), error=str(exc)))


class ChartCanvas(FigureCanvasQTAgg):
    def __init__(self) -> None:
        self.figure = Figure(figsize=(8, 4), tight_layout=True)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TSM Analytics")
        self.resize(1300, 850)

        self.csv_path = ""
        self.data = pd.DataFrame()
        self.filtered = pd.DataFrame()

        self.table_model = DataFrameTableModel()

        self._build_ui()
        self._apply_dark_theme()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        file_row = QHBoxLayout()
        self.select_file_btn = QPushButton("Select TSM Sales CSV")
        self.select_file_btn.clicked.connect(self.select_file)
        self.file_label = QLabel("No file selected")
        self.status_label = QLabel("Idle")
        file_row.addWidget(self.select_file_btn)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(self.status_label)
        layout.addLayout(file_row)

        self.mapping_group = QGroupBox("Manual Column Mapping")
        mapping_form = QFormLayout(self.mapping_group)
        self.timestamp_combo = QComboBox()
        self.price_combo = QComboBox()
        self.item_combo = QComboBox()
        self.qty_combo = QComboBox()
        self.apply_mapping_btn = QPushButton("Load with Mapping")
        self.apply_mapping_btn.clicked.connect(self.load_with_manual_mapping)
        mapping_form.addRow("Timestamp column*", self.timestamp_combo)
        mapping_form.addRow("Price column*", self.price_combo)
        mapping_form.addRow("Item column (optional)", self.item_combo)
        mapping_form.addRow("Quantity column (optional)", self.qty_combo)
        mapping_form.addRow(self.apply_mapping_btn)
        self.mapping_group.setVisible(False)
        layout.addWidget(self.mapping_group)

        filter_group = QGroupBox("Filters")
        filter_row = QHBoxLayout(filter_group)
        self.start_date = QDateEdit(calendarPopup=True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date = QDateEdit(calendarPopup=True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")

        self.item_filter = QComboBox()
        self.item_filter.setEditable(True)
        self.item_filter.setInsertPolicy(QComboBox.NoInsert)
        self.item_filter.lineEdit().setPlaceholderText("Search/select item")

        self.apply_filter_btn = QPushButton("Apply Filters")
        self.apply_filter_btn.clicked.connect(self.apply_filters)
        self.reset_filter_btn = QPushButton("Reset")
        self.reset_filter_btn.clicked.connect(self.reset_filters)

        filter_row.addWidget(QLabel("Start"))
        filter_row.addWidget(self.start_date)
        filter_row.addWidget(QLabel("End"))
        filter_row.addWidget(self.end_date)
        filter_row.addWidget(QLabel("Item"))
        filter_row.addWidget(self.item_filter, 1)
        filter_row.addWidget(self.apply_filter_btn)
        filter_row.addWidget(self.reset_filter_btn)
        layout.addWidget(filter_group)

        chart_controls = QHBoxLayout()
        self.show_price_chart = QCheckBox("Show Price Per Sale Chart")
        self.show_price_chart.setChecked(True)
        self.show_price_chart.stateChanged.connect(self.refresh_views)

        self.chart_select = QComboBox()
        self.chart_select.addItems(["Gold earned per day", "Sales count per day", "Price per sale over time"])

        self.export_chart_btn = QPushButton("Export Selected Chart PNG")
        self.export_chart_btn.clicked.connect(self.export_chart)
        self.export_data_btn = QPushButton("Export Normalized CSV")
        self.export_data_btn.clicked.connect(self.export_data)

        chart_controls.addWidget(self.show_price_chart)
        chart_controls.addWidget(QLabel("Export target"))
        chart_controls.addWidget(self.chart_select)
        chart_controls.addWidget(self.export_chart_btn)
        chart_controls.addWidget(self.export_data_btn)
        layout.addLayout(chart_controls)

        splitter = QSplitter(Qt.Vertical)
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        self.gold_canvas = ChartCanvas()
        self.sales_canvas = ChartCanvas()
        self.price_canvas = ChartCanvas()
        chart_layout.addWidget(self.gold_canvas)
        chart_layout.addWidget(self.sales_canvas)
        chart_layout.addWidget(self.price_canvas)

        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setSortingEnabled(True)

        splitter.addWidget(chart_widget)
        splitter.addWidget(self.table)
        splitter.setSizes([530, 300])
        layout.addWidget(splitter)

    def _apply_dark_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background-color: #1d2129; color: #f3f3f3; }
            QGroupBox { border: 1px solid #3a3f4b; margin-top: 8px; padding-top: 12px; }
            QPushButton { background-color: #3267b3; border-radius: 4px; padding: 7px; }
            QPushButton:hover { background-color: #3f79cc; }
            QLineEdit, QComboBox, QDateEdit, QTableView {
                background-color: #2a2f3a;
                border: 1px solid #444d5c;
                padding: 4px;
            }
            QHeaderView::section { background-color: #2f3541; color: #f3f3f3; }
        """
        )

    def select_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select TSM Sales CSV", os.path.expanduser("~"), "CSV files (*.csv)")
        if not path:
            return

        self.csv_path = path
        self.file_label.setText(path)

        try:
            headers = extract_headers(path)
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Could not read CSV", str(exc))
            return

        self.setup_mapping_ui(headers)
        guess = autodetect_mapping(headers)

        if has_required_mapping(guess):
            self.mapping_group.setVisible(False)
            self.start_loading(path, guess)
        else:
            self.mapping_group.setVisible(True)
            self.status_label.setText("Autodetect failed. Select required columns.")

    def setup_mapping_ui(self, headers: list[str]) -> None:
        optional_headers = [""] + headers
        for combo in (self.timestamp_combo, self.price_combo, self.item_combo, self.qty_combo):
            combo.clear()
        self.timestamp_combo.addItems(headers)
        self.price_combo.addItems(headers)
        self.item_combo.addItems(optional_headers)
        self.qty_combo.addItems(optional_headers)

    def load_with_manual_mapping(self) -> None:
        mapping = ColumnMapping(
            timestamp=self.timestamp_combo.currentText().strip(),
            price=self.price_combo.currentText().strip(),
            item=self.item_combo.currentText().strip() or None,
            quantity=self.qty_combo.currentText().strip() or None,
        )
        if not has_required_mapping(mapping):
            QMessageBox.warning(self, "Missing mapping", "Timestamp and Price columns are required.")
            return

        self.start_loading(self.csv_path, mapping)

    def start_loading(self, csv_path: str, mapping: ColumnMapping) -> None:
        self.status_label.setText("Loading CSV in background...")
        self.select_file_btn.setEnabled(False)
        self.apply_mapping_btn.setEnabled(False)

        self._thread = QThread(self)
        self._worker = LoaderWorker(csv_path, mapping)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.on_loaded)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def on_loaded(self, result: WorkerResult) -> None:
        self.select_file_btn.setEnabled(True)
        self.apply_mapping_btn.setEnabled(True)

        if result.error:
            self.status_label.setText("Load failed")
            QMessageBox.critical(self, "Load error", result.error)
            return

        self.data = result.frame
        self.filtered = result.frame.copy()
        self.status_label.setText(f"Loaded {len(self.data):,} rows")

        self.mapping_group.setVisible(False)
        self.setup_filter_values()
        self.refresh_views()

    def setup_filter_values(self) -> None:
        if self.data.empty:
            return

        dates = pd.to_datetime(self.data["date"])
        self.start_date.setDate(QDate(dates.min().year, dates.min().month, dates.min().day))
        self.end_date.setDate(QDate(dates.max().year, dates.max().month, dates.max().day))

        items = sorted(self.data["item"].dropna().astype(str).unique().tolist())
        self.item_filter.clear()
        self.item_filter.addItem("All Items")
        self.item_filter.addItems(items)

    def apply_filters(self) -> None:
        if self.data.empty:
            return

        start = self.start_date.date().toPython()
        end = self.end_date.date().toPython()
        selected_item = self.item_filter.currentText().strip()

        frame = self.data[(self.data["date"] >= start) & (self.data["date"] <= end)]
        if selected_item and selected_item != "All Items":
            frame = frame[frame["item"] == selected_item]

        self.filtered = frame
        self.refresh_views()

    def reset_filters(self) -> None:
        if self.data.empty:
            return
        self.filtered = self.data.copy()
        self.setup_filter_values()
        self.refresh_views()

    def refresh_views(self) -> None:
        if self.filtered.empty:
            self.table_model.set_frame(pd.DataFrame())
            for canvas in (self.gold_canvas, self.sales_canvas, self.price_canvas):
                canvas.axes.clear()
                canvas.draw_idle()
            return

        display = self.filtered.copy()
        display["local_time"] = pd.to_datetime(display["local_time"])
        self.table_model.set_frame(display[["local_time", "item", "quantity", "price_gold", "price_copper"]])

        grouped = daily_aggregates(self.filtered)

        gold = grouped["gold_per_day"]
        self.gold_canvas.axes.clear()
        self.gold_canvas.axes.plot(gold["date"], gold["price_gold"], marker="o", color="#ffd166")
        self.gold_canvas.axes.set_title("Gold Earned Per Day")
        self.gold_canvas.axes.set_ylabel("Gold")
        self.gold_canvas.axes.grid(alpha=0.2)
        self.gold_canvas.axes.tick_params(axis="x", rotation=25)
        self.gold_canvas.draw_idle()

        sales = grouped["sales_per_day"]
        self.sales_canvas.axes.clear()
        self.sales_canvas.axes.plot(sales["date"], sales["sales_count"], marker="o", color="#4fc3f7")
        self.sales_canvas.axes.set_title("Sales Count Per Day")
        self.sales_canvas.axes.set_ylabel("Sales")
        self.sales_canvas.axes.grid(alpha=0.2)
        self.sales_canvas.axes.tick_params(axis="x", rotation=25)
        self.sales_canvas.draw_idle()

        self.price_canvas.setVisible(self.show_price_chart.isChecked())
        if self.show_price_chart.isChecked():
            self.price_canvas.axes.clear()
            self.price_canvas.axes.scatter(self.filtered["local_time"], self.filtered["price_gold"], s=8, c="#90be6d")
            self.price_canvas.axes.set_title("Price Per Sale Over Time")
            self.price_canvas.axes.set_ylabel("Gold")
            self.price_canvas.axes.grid(alpha=0.2)
            self.price_canvas.axes.tick_params(axis="x", rotation=25)
            self.price_canvas.draw_idle()

    def export_chart(self) -> None:
        chart_name = self.chart_select.currentText()
        if chart_name == "Gold earned per day":
            canvas = self.gold_canvas
        elif chart_name == "Sales count per day":
            canvas = self.sales_canvas
        else:
            canvas = self.price_canvas

        if chart_name == "Price per sale over time" and not self.show_price_chart.isChecked():
            QMessageBox.warning(self, "Chart hidden", "Enable the price chart toggle before exporting this chart.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export chart", "chart.png", "PNG Image (*.png)")
        if not path:
            return

        canvas.figure.savefig(path, dpi=160)
        self.status_label.setText(f"Chart exported: {path}")

    def export_data(self) -> None:
        if self.filtered.empty:
            QMessageBox.information(self, "No data", "Load and filter data before exporting.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export normalized dataset", "normalized_sales.csv", "CSV (*.csv)")
        if not path:
            return

        self.filtered.to_csv(path, index=False)
        self.status_label.setText(f"Data exported: {path}")


def run() -> int:
    app = QApplication([])
    win = MainWindow()
    win.show()
    return app.exec()
