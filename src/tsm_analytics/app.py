from __future__ import annotations

import os
from dataclasses import dataclass

import matplotlib.dates as mdates
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
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .csv_processing import (
    ColumnMapping,
    aggregate_sales,
    autodetect_mapping,
    extract_headers,
    has_required_mapping,
    load_item_name_map,
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
        self.figure = Figure(figsize=(10, 4.5), tight_layout=True)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TSM Analytics")
        self.resize(1450, 900)

        self.csv_path = ""
        self.data = pd.DataFrame()
        self.filtered = pd.DataFrame()
        self.item_map = load_item_name_map()
        self._price_scatter = None
        self._hover_annotation = None

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

        filter_group = QGroupBox("Filters and Chart Controls")
        filter_layout = QVBoxLayout(filter_group)

        filter_row = QHBoxLayout()
        self.start_date = QDateEdit(calendarPopup=True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date = QDateEdit(calendarPopup=True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")

        self.item_filter = QComboBox()
        self.item_filter.setEditable(True)
        self.item_filter.setInsertPolicy(QComboBox.NoInsert)
        self.item_filter.lineEdit().setPlaceholderText("All Items or comma-separated item names")

        self.classic_mode_checkbox = QCheckBox("Classic Tailoring Mode")
        self.classic_mode_checkbox.setChecked(True)
        self.classic_mode_checkbox.stateChanged.connect(self.setup_filter_values)

        self.apply_filter_btn = QPushButton("Apply Filters")
        self.apply_filter_btn.clicked.connect(self.apply_filters)
        self.reset_filter_btn = QPushButton("Reset")
        self.reset_filter_btn.clicked.connect(self.reset_filters)

        filter_row.addWidget(QLabel("Start"))
        filter_row.addWidget(self.start_date)
        filter_row.addWidget(QLabel("End"))
        filter_row.addWidget(self.end_date)
        filter_row.addWidget(QLabel("Item(s)"))
        filter_row.addWidget(self.item_filter, 1)
        filter_row.addWidget(self.classic_mode_checkbox)
        filter_row.addWidget(self.apply_filter_btn)
        filter_row.addWidget(self.reset_filter_btn)
        filter_layout.addLayout(filter_row)

        control_row = QHBoxLayout()
        self.grouping_combo = QComboBox()
        self.grouping_combo.addItems(["Daily", "Hourly"])
        self.grouping_combo.currentIndexChanged.connect(self.refresh_views)

        self.show_price_chart = QCheckBox("Show Price Per Sale")
        self.show_price_chart.setChecked(True)
        self.show_price_chart.stateChanged.connect(self.refresh_views)

        self.show_ma_checkbox = QCheckBox("Show moving average")
        self.show_ma_checkbox.setChecked(True)
        self.show_ma_checkbox.stateChanged.connect(self.refresh_views)

        self.show_per_item_checkbox = QCheckBox("Per-item gold series")
        self.show_per_item_checkbox.setChecked(True)
        self.show_per_item_checkbox.stateChanged.connect(self.refresh_views)

        self.top_n_spin = QSpinBox()
        self.top_n_spin.setRange(1, 20)
        self.top_n_spin.setValue(5)
        self.top_n_spin.valueChanged.connect(self.refresh_views)

        self.chart_select = QComboBox()
        self.chart_select.addItems(["Gold earned", "Sales count", "Price per sale"])

        self.export_chart_btn = QPushButton("Export Selected Chart PNG")
        self.export_chart_btn.clicked.connect(self.export_chart)
        self.export_data_btn = QPushButton("Export Normalized CSV")
        self.export_data_btn.clicked.connect(self.export_data)

        control_row.addWidget(QLabel("Grouping"))
        control_row.addWidget(self.grouping_combo)
        control_row.addWidget(self.show_price_chart)
        control_row.addWidget(self.show_ma_checkbox)
        control_row.addWidget(self.show_per_item_checkbox)
        control_row.addWidget(QLabel("Top N"))
        control_row.addWidget(self.top_n_spin)
        control_row.addStretch(1)
        control_row.addWidget(QLabel("Export target"))
        control_row.addWidget(self.chart_select)
        control_row.addWidget(self.export_chart_btn)
        control_row.addWidget(self.export_data_btn)
        filter_layout.addLayout(control_row)

        layout.addWidget(filter_group)

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
        splitter.setSizes([560, 300])
        layout.addWidget(splitter)

        self.price_canvas.mpl_connect("motion_notify_event", self.on_price_hover)

    def _apply_dark_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background-color: #1d2129; color: #f3f3f3; font-size: 13px; }
            QGroupBox { border: 1px solid #3a3f4b; margin-top: 8px; padding-top: 12px; }
            QPushButton { background-color: #3267b3; border-radius: 4px; padding: 7px; }
            QPushButton:hover { background-color: #3f79cc; }
            QLineEdit, QComboBox, QDateEdit, QTableView, QSpinBox {
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

        items = sorted(self.data[["item_name", "item_id"]].drop_duplicates().to_dict("records"), key=lambda r: r["item_name"])
        if self.classic_mode_checkbox.isChecked():
            known_ids = set(self.item_map.keys())
            filtered_names = sorted({r["item_name"] for r in items if str(r["item_id"]) in known_ids})
            unknown_exists = any(str(r["item_id"]) not in known_ids for r in items)
            item_names = filtered_names + (["Unknown"] if unknown_exists else [])
        else:
            item_names = [r["item_name"] for r in items]

        self.item_filter.clear()
        self.item_filter.addItem("All Items")
        self.item_filter.addItems(item_names)

    def apply_filters(self) -> None:
        if self.data.empty:
            return

        start = self.start_date.date().toPython()
        end = self.end_date.date().toPython()
        selected_text = self.item_filter.currentText().strip()

        frame = self.data[(self.data["date"] >= start) & (self.data["date"] <= end)]

        if selected_text and selected_text != "All Items":
            item_names = [s.strip() for s in selected_text.split(",") if s.strip()]
            if "Unknown" in item_names:
                non_unknown = [name for name in item_names if name != "Unknown"]
                unknown_mask = frame["item_name"].str.startswith("Unknown")
                if non_unknown:
                    frame = frame[frame["item_name"].isin(non_unknown) | unknown_mask]
                else:
                    frame = frame[unknown_mask]
            else:
                frame = frame[frame["item_name"].isin(item_names)]

        self.filtered = frame
        self.refresh_views()

    def reset_filters(self) -> None:
        if self.data.empty:
            return
        self.filtered = self.data.copy()
        self.setup_filter_values()
        self.refresh_views()

    def _setup_datetime_axis(self, axes) -> None:
        locator = mdates.AutoDateLocator(minticks=4, maxticks=10)
        formatter = mdates.ConciseDateFormatter(locator)
        axes.xaxis.set_major_locator(locator)
        axes.xaxis.set_major_formatter(formatter)
        axes.grid(alpha=0.25, linestyle="--")
        axes.tick_params(axis="x", rotation=20)

    def refresh_views(self) -> None:
        if self.filtered.empty:
            self.table_model.set_frame(pd.DataFrame())
            for canvas in (self.gold_canvas, self.sales_canvas, self.price_canvas):
                canvas.axes.clear()
                canvas.draw_idle()
            return

        display_cols = [
            "local_time",
            "item_name",
            "item_id",
            "quantity",
            "price_display",
            "total_display",
            "price_copper",
            "total_copper",
        ]
        self.table_model.set_frame(self.filtered[display_cols].copy())

        freq = "D" if self.grouping_combo.currentText() == "Daily" else "H"
        by_item = self.show_per_item_checkbox.isChecked()

        dataset = self.filtered
        if by_item and self.item_filter.currentText().strip() in ("", "All Items"):
            top_n = self.top_n_spin.value()
            top_items = dataset.groupby("item_name")["total_copper"].sum().nlargest(top_n).index
            dataset = dataset[dataset["item_name"].isin(top_items)]

        grouped = aggregate_sales(dataset, freq=freq, by_item=by_item)

        self.gold_canvas.axes.clear()
        self.gold_canvas.axes.set_title("Gold Earned Over Time", fontsize=14)
        self.gold_canvas.axes.set_ylabel("Gold", fontsize=11)

        if by_item and not grouped["gold"].empty and "item_name" in grouped["gold"].columns:
            for item_name, subset in grouped["gold"].groupby("item_name"):
                self.gold_canvas.axes.plot(subset["local_time"], subset["gold"], marker="o", linewidth=1.8, label=item_name)
            self.gold_canvas.axes.legend(loc="upper left", fontsize=9)
        else:
            gold = grouped["gold"]
            self.gold_canvas.axes.plot(gold["local_time"], gold["gold"], marker="o", color="#ffd166", linewidth=2)

            if self.show_ma_checkbox.isChecked() and freq == "D":
                ma = gold["gold"].rolling(7, min_periods=1).mean()
                self.gold_canvas.axes.plot(gold["local_time"], ma, color="#ff9f1c", linewidth=2.2, linestyle="--", label="7-day MA")
                self.gold_canvas.axes.legend(loc="upper left", fontsize=9)

        self._setup_datetime_axis(self.gold_canvas.axes)
        self.gold_canvas.draw_idle()

        sales = grouped["sales"]
        self.sales_canvas.axes.clear()
        self.sales_canvas.axes.set_title("Sales Count Over Time", fontsize=14)
        self.sales_canvas.axes.set_ylabel("Sales", fontsize=11)
        width = 0.8 if freq == "D" else 0.03
        self.sales_canvas.axes.bar(sales["local_time"], sales["sales_count"], color="#4fc3f7", width=width, align="center")
        self._setup_datetime_axis(self.sales_canvas.axes)
        self.sales_canvas.draw_idle()

        self.price_canvas.setVisible(self.show_price_chart.isChecked())
        self._price_scatter = None
        self._hover_annotation = None

        if self.show_price_chart.isChecked():
            self.price_canvas.axes.clear()
            self.price_canvas.axes.set_title("Price Per Sale", fontsize=14)
            self.price_canvas.axes.set_ylabel("Price (Gold)", fontsize=11)
            self._price_scatter = self.price_canvas.axes.scatter(
                self.filtered["local_time"],
                self.filtered["price_gold"],
                s=14,
                c="#90be6d",
                alpha=0.8,
            )
            self._setup_datetime_axis(self.price_canvas.axes)
            self.price_canvas.draw_idle()

    def on_price_hover(self, event) -> None:
        if not self._price_scatter or event.inaxes != self.price_canvas.axes or self.filtered.empty:
            return

        contains, details = self._price_scatter.contains(event)
        if not contains:
            if self._hover_annotation is not None:
                self._hover_annotation.set_visible(False)
                self.price_canvas.draw_idle()
            return

        point_index = details["ind"][0]
        row = self.filtered.iloc[point_index]
        text = (
            f"{row['item_name']}\n"
            f"Time: {pd.to_datetime(row['local_time']).strftime('%Y-%m-%d %H:%M')}\n"
            f"Qty: {row['quantity']}\n"
            f"Price: {row['price_display']}\n"
            f"Total: {row['total_display']}"
        )

        if self._hover_annotation is None:
            self._hover_annotation = self.price_canvas.axes.annotate(
                text,
                xy=(event.xdata, event.ydata),
                xytext=(12, 12),
                textcoords="offset points",
                bbox={"boxstyle": "round", "fc": "#11151c", "ec": "#4fc3f7", "alpha": 0.95},
                color="white",
                fontsize=9,
            )
        else:
            self._hover_annotation.set_text(text)
            self._hover_annotation.xy = (event.xdata, event.ydata)
            self._hover_annotation.set_visible(True)

        self.price_canvas.draw_idle()

    def export_chart(self) -> None:
        chart_name = self.chart_select.currentText()
        if chart_name == "Gold earned":
            canvas = self.gold_canvas
        elif chart_name == "Sales count":
            canvas = self.sales_canvas
        else:
            canvas = self.price_canvas

        if chart_name == "Price per sale" and not self.show_price_chart.isChecked():
            QMessageBox.warning(self, "Chart hidden", "Enable the price chart toggle before exporting this chart.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export chart", "chart.png", "PNG Image (*.png)")
        if not path:
            return

        canvas.figure.set_size_inches(19.2, 10.8)
        canvas.figure.savefig(path, dpi=100, bbox_inches="tight")
        self.status_label.setText(f"Chart exported: {path}")

    def export_data(self) -> None:
        if self.filtered.empty:
            QMessageBox.information(self, "No data", "Load and filter data before exporting.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export normalized dataset", "normalized_sales.csv", "CSV (*.csv)")
        if not path:
            return

        export_cols = [
            "local_time",
            "date",
            "item",
            "item_id",
            "item_name",
            "quantity",
            "price_copper",
            "price_display",
            "total_copper",
            "total_display",
            "total_gold",
        ]
        self.filtered[export_cols].to_csv(path, index=False)
        self.status_label.setText(f"Data exported: {path}")


def run() -> int:
    app = QApplication([])
    win = MainWindow()
    win.show()
    return app.exec()
