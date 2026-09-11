"""車輛清單的資料模型。

舊工具用一個純清單框列出所有車輛。上千台車時那是不能用的——找一台車要
自己捲，也看不出哪些是行人、哪些是不完整軌跡。這裡改成可勾選、可搜尋、
可依車種與品質篩選的表格。
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor

from ._session import CLASS_NAMES

_COLUMNS = ("車號", "車種", "路線", "影格")


class VehicleTableModel(QAbstractTableModel):
    """一列一台車，第一欄可勾選。"""

    selection_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []
        self._checked: set[str] = set()
        self._colors: dict[str, tuple[int, int, int]] = {}

    # ------------------------------------------------------------ 資料載入

    def set_vehicles(self, vehicles: pd.DataFrame) -> None:
        self.beginResetModel()
        self._rows = [
            {
                "vehicle_id": str(row.vehicle_id),
                "vehicle_class": str(row.vehicle_class),
                "entry_gate": str(row.entry_gate),
                "exit_gate": str(row.exit_gate),
                "entry_frame": int(row.entry_frame),
                "exit_frame": int(row.exit_frame),
                "is_complete": bool(row.is_complete),
                "is_crosswalk": bool(row.is_crosswalk),
            }
            for row in vehicles.itertuples(index=False)
        ]
        self._checked.clear()
        self._colors.clear()
        self.endResetModel()
        self.selection_changed.emit()

    def set_colors(self, colors: dict[str, tuple[int, int, int]]) -> None:
        """更新色塊。顏色由選取順序決定，所以每次選取變動都要重設。"""
        self._colors = dict(colors)
        if self._rows:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._rows) - 1, 0),
                [Qt.ItemDataRole.DecorationRole],
            )

    # ------------------------------------------------------------ Qt 介面

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return _COLUMNS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return row["vehicle_id"]
            if column == 1:
                code = row["vehicle_class"]
                return f"{CLASS_NAMES.get(code, code)}"
            if column == 2:
                return f"{row['entry_gate']}→{row['exit_gate']}"
            return f"{row['entry_frame']}–{row['exit_frame']}"

        if role == Qt.ItemDataRole.CheckStateRole and column == 0:
            return (
                Qt.CheckState.Checked if row["vehicle_id"] in self._checked
                else Qt.CheckState.Unchecked
            )

        if role == Qt.ItemDataRole.DecorationRole and column == 0:
            color = self._colors.get(row["vehicle_id"])
            if color is not None:
                blue, green, red = color
                return QColor(red, green, blue)

        if role == Qt.ItemDataRole.ToolTipRole:
            notes = []
            if not row["is_complete"]:
                notes.append("不完整軌跡（代號 X）")
            if row["is_crosswalk"]:
                notes.append("行穿線代號")
            return "\n".join(notes) if notes else None

        if role == Qt.ItemDataRole.ForegroundRole and not row["is_complete"]:
            # 不完整的軌跡灰掉，但**不隱藏**——要不要用是使用者的決定。
            return QColor(140, 140, 140)

        if role == Qt.ItemDataRole.UserRole:
            return row

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or index.column() != 0:
            return False
        if role != Qt.ItemDataRole.CheckStateRole:
            return False

        vehicle_id = self._rows[index.row()]["vehicle_id"]
        if Qt.CheckState(value) == Qt.CheckState.Checked:
            self._checked.add(vehicle_id)
        else:
            self._checked.discard(vehicle_id)
        self.dataChanged.emit(index, index, [role])
        self.selection_changed.emit()
        return True

    # ------------------------------------------------------------ 選取操作

    def selected_ids(self) -> list[str]:
        """依**表格順序**回傳選取的車號，配色就照這個順序。"""
        return [
            row["vehicle_id"] for row in self._rows
            if row["vehicle_id"] in self._checked
        ]

    def all_ids(self) -> list[str]:
        return [row["vehicle_id"] for row in self._rows]

    def set_checked(self, vehicle_ids) -> list[str]:
        """整批設定選取，回傳清單裡找不到的車號。"""
        known = {row["vehicle_id"] for row in self._rows}
        wanted = [str(item) for item in vehicle_ids]
        self._checked = {item for item in wanted if item in known}
        self._emit_all_changed()
        return [item for item in wanted if item not in known]

    def check_rows(self, rows, checked: bool) -> None:
        for row in rows:
            if 0 <= row < len(self._rows):
                vehicle_id = self._rows[row]["vehicle_id"]
                if checked:
                    self._checked.add(vehicle_id)
                else:
                    self._checked.discard(vehicle_id)
        self._emit_all_changed()

    def clear_selection(self) -> None:
        self._checked.clear()
        self._emit_all_changed()

    def _emit_all_changed(self) -> None:
        if self._rows:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._rows) - 1, 0)
            )
        self.selection_changed.emit()


def matches_filter(
    row: dict,
    *,
    text: str = "",
    vehicle_class: str | None = None,
    complete_only: bool = False,
    hide_crosswalk: bool = False,
) -> bool:
    """這一列符不符合目前的篩選條件。

    ``text`` 是**單純的子字串比對**，範圍是車號、車種代號與路線。
    因此輸入 ``"B→"`` 除了從 B 進入的車，也會命中行穿線代號 ``"AB→AB"``——
    這是子字串比對的必然結果。想只留一般路口代號，請搭配「隱藏行穿線」。
    """
    if complete_only and not row["is_complete"]:
        return False
    if hide_crosswalk and row["is_crosswalk"]:
        return False
    if vehicle_class and row["vehicle_class"] != vehicle_class:
        return False
    if text:
        needle = text.strip().lower()
        haystack = (
            f"{row['vehicle_id']} {row['vehicle_class']} "
            f"{row['entry_gate']}→{row['exit_gate']}"
        ).lower()
        if needle not in haystack:
            return False
    return True
