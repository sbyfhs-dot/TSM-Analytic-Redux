from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class DataFrameTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._frame = pd.DataFrame()

    def set_frame(self, frame: pd.DataFrame) -> None:
        self.beginResetModel()
        self._frame = frame.reset_index(drop=True).copy()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._frame)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._frame.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        value = self._frame.iloc[index.row(), index.column()]
        if role == Qt.ToolTipRole:
            return str(value)
        if role not in (Qt.DisplayRole, Qt.EditRole):
            return None

        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, float):
            return f"{value:.4f}"
        return str(value)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # noqa: N802
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._frame.columns[section] if section < len(self._frame.columns) else ""
        return str(section + 1)
