"""主視窗。

版面的原則是**預覽最大、設定最小**：畫面中央永遠是你要確認的那張圖，
左邊是選車，下面一條是設定。常用的四個外觀選項留在外面，其餘收進「進階」。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .._colors import NAMED_COLORS, assign_colors
from .._video import CODECS
from ._preview import PreviewController, PreviewView
from ._session import (
    CLASS_NAMES,
    Appearance,
    Session,
    parse_id_list,
    summarise_id_list,
)
from ._vehicles import VehicleTableModel, matches_filter
from ._worker import RenderWorker

_LABEL_CHOICES = [("不顯示", "none"), ("車號", "id"),
                  ("車種", "class"), ("車號＋車種", "both")]
_FRONT_CHOICES = [("不標示", "none"), ("車頭邊", "edge"),
                  ("箭頭", "arrow"), ("兩者", "both")]

_STYLESHEET = """
QMainWindow, QWidget { font-size: 13px; }
QGroupBox {
    border: 1px solid palette(mid); border-radius: 6px;
    margin-top: 10px; padding: 10px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px; padding: 0 4px;
    color: palette(dark);
}
QPushButton { padding: 5px 14px; border-radius: 4px; }
QPushButton#primary { font-weight: 600; padding: 7px 18px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    padding: 4px 6px; border-radius: 4px;
}
QTableView { border: 1px solid palette(mid); border-radius: 6px; }
QLabel#hint { color: palette(dark); }
"""


class MainWindow(QMainWindow):
    """空拍影片車輛標註工具。"""

    preview_needed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TrafficKit 車輛標註")
        self.resize(1280, 820)
        self.setStyleSheet(_STYLESHEET)

        self.session = Session()
        self.model = VehicleTableModel(self)
        self._thread: QThread | None = None
        self._worker: RenderWorker | None = None

        self._build()
        self._connect()
        self._update_enabled()

    # ------------------------------------------------------------ 版面

    def _build(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(10)

        layout.addWidget(self._build_sources())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_vehicles())
        splitter.addWidget(self._build_preview())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 900])
        layout.addWidget(splitter, stretch=1)

        layout.addWidget(self._build_settings())
        layout.addLayout(self._build_actions())

        self.setCentralWidget(root)
        self.statusBar().showMessage("請先選擇影片與軌跡檔")

    def _build_sources(self) -> QWidget:
        box = QGroupBox("來源")
        grid = QGridLayout(box)
        grid.setColumnStretch(1, 1)

        self.video_edit = QLineEdit(readOnly=True, placeholderText="尚未選擇影片")
        self.tracks_edit = QLineEdit(
            readOnly=True, placeholderText="尚未選擇軌跡檔（MOTC_SU 格式）"
        )
        self.video_button = QPushButton("選擇影片…")
        self.tracks_button = QPushButton("選擇軌跡檔…")

        grid.addWidget(QLabel("影片"), 0, 0)
        grid.addWidget(self.video_edit, 0, 1)
        grid.addWidget(self.video_button, 0, 2)
        grid.addWidget(QLabel("軌跡"), 1, 0)
        grid.addWidget(self.tracks_edit, 1, 1)
        grid.addWidget(self.tracks_button, 1, 2)
        return box

    def _build_vehicles(self) -> QWidget:
        box = QGroupBox("車輛")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        filters = QHBoxLayout()
        self.search_edit = QLineEdit(placeholderText="搜尋車號、車種或路線")
        self.class_filter = QComboBox()
        self.class_filter.addItem("全部車種", None)
        for code, name in CLASS_NAMES.items():
            self.class_filter.addItem(name, code)
        filters.addWidget(self.search_edit, stretch=1)
        filters.addWidget(self.class_filter)
        layout.addLayout(filters)

        toggles = QHBoxLayout()
        self.complete_only = QCheckBox("只顯示完整軌跡")
        self.hide_crosswalk = QCheckBox("隱藏行穿線")
        self.complete_only.setToolTip(
            "代號 X 代表軌跡不完整。灰色那幾列就是，預設仍然列出來讓你自己決定。"
        )
        toggles.addWidget(self.complete_only)
        toggles.addWidget(self.hide_crosswalk)
        toggles.addStretch(1)
        layout.addLayout(toggles)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        header = self.table.horizontalHeader()
        for column in range(3):
            header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        buttons = QHBoxLayout()
        self.select_shown = QPushButton("勾選目前顯示")
        self.clear_selection = QPushButton("全部取消")
        buttons.addWidget(self.select_shown)
        buttons.addWidget(self.clear_selection)
        layout.addLayout(buttons)

        typed = QHBoxLayout()
        self.id_edit = QLineEdit(placeholderText="直接輸入：2,4,5 或 10-15")
        self.id_apply = QPushButton("套用")
        typed.addWidget(self.id_edit, stretch=1)
        typed.addWidget(self.id_apply)
        layout.addLayout(typed)

        self.selection_label = QLabel("已選 0 台")
        self.selection_label.setObjectName("hint")
        layout.addWidget(self.selection_label)
        return box

    def _build_preview(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.preview_view = PreviewView()
        self.preview = PreviewController(self.preview_view, self)
        layout.addWidget(self.preview_view, stretch=1)

        timeline = QHBoxLayout()
        self.prev_button = QToolButton(text="◀")
        self.next_button = QToolButton(text="▶")
        self.frame_slider = _Slider()
        self.frame_spin = QSpinBox()
        self.frame_spin.setFixedWidth(90)
        self.time_label = QLabel("—")
        self.time_label.setObjectName("hint")
        self.time_label.setFixedWidth(90)

        timeline.addWidget(self.prev_button)
        timeline.addWidget(self.frame_slider, stretch=1)
        timeline.addWidget(self.next_button)
        timeline.addWidget(QLabel("影格"))
        timeline.addWidget(self.frame_spin)
        timeline.addWidget(self.time_label)
        layout.addLayout(timeline)
        return panel

    def _build_settings(self) -> QWidget:
        box = QGroupBox("輸出設定")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        # ---- 範圍
        range_row = QHBoxLayout()
        self.range_selected = QRadioButton("所選車輛出現的範圍")
        self.range_whole = QRadioButton("整段影片")
        self.range_custom = QRadioButton("自訂")
        self.range_selected.setChecked(True)
        self.start_spin = QSpinBox()
        self.end_spin = QSpinBox()
        for spin in (self.start_spin, self.end_spin):
            spin.setFixedWidth(100)
            spin.setEnabled(False)
        range_row.addWidget(QLabel("範圍"))
        range_row.addWidget(self.range_selected)
        range_row.addWidget(self.range_whole)
        range_row.addWidget(self.range_custom)
        range_row.addWidget(QLabel("起"))
        range_row.addWidget(self.start_spin)
        range_row.addWidget(QLabel("迄"))
        range_row.addWidget(self.end_spin)
        range_row.addStretch(1)
        layout.addLayout(range_row)

        # ---- 常用外觀
        common = QHBoxLayout()
        self.label_combo = _combo(_LABEL_CHOICES, "id")
        self.front_combo = _combo(_FRONT_CHOICES, "arrow")
        self.thickness_spin = QSpinBox()
        self.thickness_spin.setRange(1, 12)
        self.thickness_spin.setValue(2)
        self.front_color = QComboBox()
        for name in ("white", "yellow", "cyan", "magenta", "black"):
            self.front_color.addItem(_swatch(name), name, name)

        common.addWidget(QLabel("標籤"))
        common.addWidget(self.label_combo)
        common.addWidget(QLabel("車頭"))
        common.addWidget(self.front_combo)
        common.addWidget(QLabel("框線"))
        common.addWidget(self.thickness_spin)
        common.addWidget(QLabel("車頭色"))
        common.addWidget(self.front_color)
        common.addStretch(1)

        self.advanced_toggle = QToolButton(text="進階")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.advanced_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        common.addWidget(self.advanced_toggle)
        layout.addLayout(common)

        layout.addWidget(self._build_advanced())
        return box

    def _build_advanced(self) -> QWidget:
        self.advanced = QFrame()
        self.advanced.setVisible(False)
        grid = QGridLayout(self.advanced)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(14)

        self.fill_spin = _double(0.0, 1.0, 0.05, 0.0)
        self.font_spin = _double(0.2, 3.0, 0.1, 0.6)
        self.smooth_spin = QSpinBox()
        self.smooth_spin.setRange(0, 60)
        self.smooth_spin.setValue(5)
        self.interpolate_check = QCheckBox("取樣間補格")
        self.interpolate_check.setChecked(True)
        self.gap_spin = QSpinBox()
        self.gap_spin.setRange(0, 600)
        self.gap_spin.setValue(30)
        self.frame_number_check = QCheckBox("疊上影格與時間")
        self.scale_spin = _double(0.1, 1.0, 0.05, 1.0)
        self.codec_combo = QComboBox()
        for name in CODECS:
            self.codec_combo.addItem(f"{name}（{CODECS[name][1]}）", name)

        entries = [
            ("框內填色", self.fill_spin, "0 為不填，1 為不透明"),
            ("標籤字體", self.font_spin, None),
            ("箭頭平滑", self.smooth_spin, "取前後各 N 格的平均方向，0 為不平滑"),
            ("內插上限", self.gap_spin,
             "相鄰取樣點相隔超過這麼多格就不補；防止車子開走了框還留著"),
            ("輸出縮放", self.scale_spin, "0.5 為長寬各半"),
            ("編碼", self.codec_combo, "MJPG 最快，mp4v 相容性佳"),
        ]
        for column, (title, widget, tip) in enumerate(entries):
            label = QLabel(title)
            if tip:
                label.setToolTip(tip)
                widget.setToolTip(tip)
            grid.addWidget(label, 0, column)
            grid.addWidget(widget, 1, column)

        checks = QHBoxLayout()
        checks.addWidget(self.interpolate_check)
        checks.addWidget(self.frame_number_check)
        checks.addStretch(1)
        grid.addLayout(checks, 2, 0, 1, len(entries))
        grid.setColumnStretch(len(entries), 1)
        return self.advanced

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(18)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setVisible(False)
        self.render_button = QPushButton("輸出影片…")
        self.render_button.setObjectName("primary")
        self.render_button.setDefault(True)

        row.addWidget(self.progress, stretch=1)
        # 進度條平常是隱藏的，隱藏的 widget 不佔版面也不提供 stretch，
        # 少了這一行按鈕會跑到視窗正中央。
        row.addStretch(1)
        row.addWidget(self.cancel_button)
        row.addWidget(self.render_button)
        return row

    # ------------------------------------------------------------ 連線

    def _connect(self) -> None:
        self.video_button.clicked.connect(self._pick_video)
        self.tracks_button.clicked.connect(self._pick_tracks)

        self.search_edit.textChanged.connect(self._apply_filter)
        self.class_filter.currentIndexChanged.connect(self._apply_filter)
        self.complete_only.toggled.connect(self._apply_filter)
        self.hide_crosswalk.toggled.connect(self._apply_filter)

        self.select_shown.clicked.connect(self._select_shown)
        self.clear_selection.clicked.connect(self.model.clear_selection)
        self.id_apply.clicked.connect(self._apply_typed_ids)
        self.id_edit.returnPressed.connect(self._apply_typed_ids)
        self.model.selection_changed.connect(self._on_selection_changed)

        self.frame_slider.valueChanged.connect(self.frame_spin.setValue)
        self.frame_spin.valueChanged.connect(self.frame_slider.setValue)
        self.frame_spin.valueChanged.connect(self._on_frame_changed)
        self.prev_button.clicked.connect(lambda: self.frame_spin.stepBy(-1))
        self.next_button.clicked.connect(lambda: self.frame_spin.stepBy(1))

        for widget in (self.label_combo, self.front_combo, self.front_color,
                       self.codec_combo):
            widget.currentIndexChanged.connect(self._refresh_preview)
        for widget in (self.thickness_spin, self.smooth_spin, self.gap_spin):
            widget.valueChanged.connect(self._refresh_preview)
        for widget in (self.fill_spin, self.font_spin, self.scale_spin):
            widget.valueChanged.connect(self._refresh_preview)
        self.interpolate_check.toggled.connect(self._refresh_preview)

        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        for button in (self.range_selected, self.range_whole, self.range_custom):
            button.toggled.connect(self._on_range_mode)

        self.render_button.clicked.connect(self._start_render)
        self.cancel_button.clicked.connect(self._cancel_render)
        self.preview.failed.connect(
            lambda message: self.statusBar().showMessage(message, 8000)
        )

        quit_action = QAction(self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    # ------------------------------------------------------------ 載入

    def _pick_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇空拍影片", "",
            "影片檔 (*.mp4 *.avi *.mov *.mkv *.MP4 *.AVI);;所有檔案 (*)",
        )
        if not path:
            return
        try:
            info = self.session.load_video(path)
            self.preview.open(path)
        except (ValueError, FileNotFoundError) as error:
            self._warn("無法讀取影片", str(error))
            return

        self.video_edit.setText(path)
        last = max(0, info.frame_count - 1)
        for widget in (self.frame_slider, self.frame_spin,
                       self.start_spin, self.end_spin):
            widget.setRange(0, last)
        self.end_spin.setValue(last)
        self.statusBar().showMessage(
            f"影片：{info.frame_count} 格、{info.fps:.2f} fps、"
            f"{info.width}×{info.height}"
        )
        self._update_enabled()
        self._refresh_preview()

    def _pick_tracks(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 MOTC_SU 軌跡檔", "", "CSV (*.csv);;所有檔案 (*)"
        )
        if not path:
            return
        try:
            summary = self.session.load_tracks(path)
        except (ValueError, FileNotFoundError) as error:
            self._warn("無法讀取軌跡檔", str(error))
            return

        self.tracks_edit.setText(path)
        self.model.set_vehicles(self.session.vehicles)
        self._apply_filter()
        self.statusBar().showMessage(summary.describe())
        self._update_enabled()

    # ------------------------------------------------------------ 選取

    def _apply_filter(self) -> None:
        text = self.search_edit.text()
        wanted_class = self.class_filter.currentData()
        for row in range(self.model.rowCount()):
            data = self.model.index(row, 0).data(Qt.ItemDataRole.UserRole)
            visible = matches_filter(
                data, text=text, vehicle_class=wanted_class,
                complete_only=self.complete_only.isChecked(),
                hide_crosswalk=self.hide_crosswalk.isChecked(),
            )
            self.table.setRowHidden(row, not visible)

    def _select_shown(self) -> None:
        rows = [row for row in range(self.model.rowCount())
                if not self.table.isRowHidden(row)]
        self.model.check_rows(rows, True)

    def _apply_typed_ids(self) -> None:
        wanted = parse_id_list(self.id_edit.text())
        unknown = self.model.set_checked(wanted)
        if unknown:
            shown = "、".join(unknown[:8]) + ("…" if len(unknown) > 8 else "")
            self.statusBar().showMessage(f"軌跡檔裡沒有這些車號：{shown}", 6000)

    def _on_selection_changed(self) -> None:
        selected = self.model.selected_ids()
        self.selection_label.setText(f"已選 {len(selected)} 台")
        self.model.set_colors(assign_colors(selected) if selected else {})
        if selected and self.id_edit.text().strip() == "":
            self.id_edit.setPlaceholderText(summarise_id_list(selected)[:40])
        if self.range_selected.isChecked():
            self._sync_range_spins()
        self._update_enabled()
        self._refresh_preview()

    # ------------------------------------------------------------ 預覽

    def _on_frame_changed(self, frame: int) -> None:
        if self.session.video is not None:
            self.time_label.setText(f"t={frame / self.session.video.fps:.2f}s")
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if not self.session.is_ready:
            return
        selected = self.model.selected_ids()
        appearance = self.appearance()
        frame = self.frame_spin.value()
        boxes = (
            self.session.boxes_for_frame(frame, selected, appearance)
            if selected else self.session.boxes_for_frame(frame, [], appearance)
        )
        self.preview.request(
            frame, boxes, self.session.style_for(selected, appearance)
        )

    def _toggle_advanced(self, shown: bool) -> None:
        self.advanced.setVisible(shown)
        self.advanced_toggle.setArrowType(
            Qt.ArrowType.DownArrow if shown else Qt.ArrowType.RightArrow
        )

    # ------------------------------------------------------------ 範圍

    def _on_range_mode(self) -> None:
        custom = self.range_custom.isChecked()
        self.start_spin.setEnabled(custom)
        self.end_spin.setEnabled(custom)
        if not custom:
            self._sync_range_spins()

    def _sync_range_spins(self) -> None:
        start, end = self.output_range()
        self.start_spin.setValue(start)
        self.end_spin.setValue(end)

    def output_range(self) -> tuple[int, int]:
        """目前設定要輸出的影格範圍。"""
        video = self.session.video
        last = max(0, (video.frame_count - 1) if video else 0)
        if self.range_custom.isChecked():
            return self.start_spin.value(), self.end_spin.value()
        if self.range_whole.isChecked() or not self.model.selected_ids():
            return 0, last
        return self.session.suggested_range(self.model.selected_ids())

    def appearance(self) -> Appearance:
        """把介面上的控制項讀成一個 :class:`Appearance`。"""
        return Appearance(
            label=self.label_combo.currentData(),
            front=self.front_combo.currentData(),
            thickness=self.thickness_spin.value(),
            front_color=self.front_color.currentData(),
            fill_alpha=self.fill_spin.value(),
            font_scale=self.font_spin.value(),
            heading_window=self.smooth_spin.value(),
            interpolate=self.interpolate_check.isChecked(),
            max_gap=self.gap_spin.value(),
            show_frame_number=self.frame_number_check.isChecked(),
            out_scale=self.scale_spin.value(),
            codec=self.codec_combo.currentData(),
        )

    # ------------------------------------------------------------ 輸出

    def _start_render(self) -> None:
        selected = self.model.selected_ids()
        if not self.session.is_ready or not selected:
            return

        appearance = self.appearance()
        start, end = self.output_range()
        if end < start:
            self._warn("範圍不對", "結束影格早於起始影格。")
            return

        suggested = str(
            Path(self.video_edit.text()).with_name(
                Path(self.video_edit.text()).stem + "_bbox"
            )
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "輸出影片", suggested,
            f"影片 (*{CODECS[appearance.codec][1]})",
        )
        if not path:
            return

        self.statusBar().showMessage("正在準備軌跡…")
        tracks = self.session.dense_tracks(selected, start, end, appearance)
        if tracks.empty:
            self._warn("沒有東西可以畫", "所選車輛在這個範圍內沒有軌跡。")
            self.statusBar().clearMessage()
            return

        self._worker = RenderWorker(
            video_path=Path(self.video_edit.text()),
            tracks=tracks,
            style=self.session.style_for(selected, appearance),
            output_path=Path(path),
            start_frame=start,
            end_frame=end,
            codec=appearance.codec,
            out_scale=appearance.out_scale,
            show_frame_number=appearance.show_frame_number,
        )
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_render_finished)
        self._worker.failed.connect(self._on_render_failed)
        self._thread.start()
        self._set_rendering(True)

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    def _on_render_finished(self, result) -> None:
        self._stop_thread()
        self._set_rendering(False)
        if result.cancelled:
            self.statusBar().showMessage(
                f"已取消，{result.frames_written} 格已寫入 {result.output_path.name}"
            )
            return
        message = (
            f"完成：{result.frames_written} 格 → {result.output_path.name}"
        )
        if result.missing_vehicle_ids:
            message += f"（{len(result.missing_vehicle_ids)} 台在這段沒有軌跡）"
        self.statusBar().showMessage(message)

    def _on_render_failed(self, message: str) -> None:
        self._stop_thread()
        self._set_rendering(False)
        self._warn("輸出失敗", message)

    def _cancel_render(self) -> None:
        if self._worker is not None:
            self._worker.cancel.set()
            self.cancel_button.setEnabled(False)

    def _stop_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
            self._thread = None
        self._worker = None

    def _set_rendering(self, active: bool) -> None:
        self.progress.setVisible(active)
        self.cancel_button.setVisible(active)
        self.cancel_button.setEnabled(active)
        self.render_button.setEnabled(not active)
        if not active:
            self.progress.reset()

    # ------------------------------------------------------------ 雜項

    def _update_enabled(self) -> None:
        ready = self.session.is_ready
        has_selection = bool(self.model.selected_ids())
        self.render_button.setEnabled(ready and has_selection)
        self.render_button.setToolTip(
            "" if ready and has_selection
            else "需要先選好影片、軌跡檔，並勾選至少一台車"
        )

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event) -> None:  # noqa: N802 （Qt 命名）
        if self._worker is not None:
            self._worker.cancel.set()
        self._stop_thread()
        self.preview.close()
        super().closeEvent(event)


class _Slider(QWidget):
    """把 QSlider 包一層，只是為了讓 import 集中在這個檔案。"""

    valueChanged = Signal(int)  # noqa: N815 （對齊 Qt 命名）

    def __init__(self, parent=None) -> None:
        from PySide6.QtWidgets import QSlider

        super().__init__(parent)
        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._slider)
        self._slider.valueChanged.connect(self.valueChanged)

    def setRange(self, low: int, high: int) -> None:  # noqa: N802
        self._slider.setRange(low, high)

    def setValue(self, value: int) -> None:  # noqa: N802
        self._slider.setValue(value)

    def value(self) -> int:
        return self._slider.value()


def _combo(choices, default) -> QComboBox:
    combo = QComboBox()
    for title, value in choices:
        combo.addItem(title, value)
    combo.setCurrentIndex([value for _, value in choices].index(default))
    return combo


def _double(low, high, step, value) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(low, high)
    spin.setSingleStep(step)
    spin.setValue(value)
    return spin


def _swatch(name: str):
    from PySide6.QtGui import QPixmap

    blue, green, red = NAMED_COLORS[name]
    pixmap = QPixmap(14, 14)
    pixmap.fill(QColor(red, green, blue))
    return pixmap
