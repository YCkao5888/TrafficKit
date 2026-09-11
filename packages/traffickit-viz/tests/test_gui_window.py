"""主視窗的規格測試。

用 Qt 的 ``offscreen`` 平台跑，不需要螢幕，因此 CI 也能驗。測的是**接線**：
按鈕有沒有接到動作、篩選有沒有生效、介面上的設定有沒有正確讀成
``Appearance``、輸出範圍三種模式算不算得對。畫面好不好看測不出來，
那要用眼睛看。
"""

import os
import tempfile
import unittest
from pathlib import Path

# 必須在建立 QApplication 之前設定，否則沒有螢幕的環境會直接當掉。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2                                                    # noqa: E402
import numpy as np                                            # noqa: E402
from PySide6.QtCore import Qt                                 # noqa: E402
from PySide6.QtWidgets import QApplication                    # noqa: E402

from traffickit_viz.gui._window import MainWindow             # noqa: E402

WIDTH, HEIGHT, FPS, FRAMES = 240, 160, 10.0, 30


def box_points(left, top, size):
    return [(left + size, top), (left + size, top + size),
            (left, top + size), (left, top)]


def make_material(directory: Path) -> tuple[Path, Path]:
    """造一段影片與對得上的 MOTC_SU 軌跡檔。

    車 1 汽車 B→A、車 2 機車 A→C、車 3 行人走行穿線、車 4 不完整（X）。
    """
    movers = [
        {"id": 1, "cls": "c", "gates": ("BI", "AO"), "x0": 10.0, "dx": 5.0, "y": 20},
        {"id": 2, "cls": "m", "gates": ("AI", "CO"), "x0": 60.0, "dx": 3.0, "y": 60},
        {"id": 3, "cls": "p", "gates": ("AB", "AB"), "x0": 100.0, "dx": 0.5, "y": 100},
        {"id": 4, "cls": "m", "gates": ("X", "CO"), "x0": 150.0, "dx": -2.0, "y": 130},
    ]
    video = directory / "clip.avi"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (WIDTH, HEIGHT)
    )
    coordinates = {mover["id"]: [] for mover in movers}
    for frame in range(FRAMES):
        image = np.full((HEIGHT, WIDTH, 3), 50, dtype=np.uint8)
        for mover in movers:
            x = mover["x0"] + mover["dx"] * frame
            cv2.rectangle(
                image, (int(x), mover["y"]), (int(x) + 16, mover["y"] + 12),
                (200, 200, 200), -1,
            )
            coordinates[mover["id"]].extend(
                value for point in box_points(x, mover["y"], 14)
                for value in point
            )
        writer.write(image)
    writer.release()

    tracks = directory / "clip_CSV_SU.csv"
    tracks.write_text(
        "\n".join(
            f"{mover['id']},0,{FRAMES - 1},{mover['gates'][0]},"
            f"{mover['gates'][1]},{mover['cls']},"
            + ",".join(f"{value:.1f}" for value in coordinates[mover["id"]])
            for mover in movers
        ) + "\n",
        encoding="utf-8",
    )
    return video, tracks


class WindowCase(unittest.TestCase):
    app: QApplication

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.video, self.tracks = make_material(self.root)

        self.window = MainWindow()
        # Qt 裡，未顯示視窗的子元件一律回報 isVisible() 為 False，
        # 所以要驗「進階區塊有沒有展開」這種事，視窗必須先 show。
        # offscreen 平台不會真的開視窗，成本很低。
        self.window.show()
        self.addCleanup(self.window.close)

    def load(self):
        """走跟按鈕一樣的路徑，只是跳過檔案對話框。"""
        info = self.window.session.load_video(self.video)
        self.window.preview.open(self.video)
        self.window.video_edit.setText(str(self.video))
        for widget in (self.window.frame_slider, self.window.frame_spin,
                       self.window.start_spin, self.window.end_spin):
            widget.setRange(0, info.frame_count - 1)
        summary = self.window.session.load_tracks(self.tracks)
        self.window.tracks_edit.setText(str(self.tracks))
        self.window.model.set_vehicles(self.window.session.vehicles)
        self.window._apply_filter()
        self.window._update_enabled()
        return summary


class TestInitialState(WindowCase):
    def test_window_builds_with_nothing_loaded(self):
        self.assertFalse(self.window.session.is_ready)
        self.assertEqual(self.window.model.rowCount(), 0)

    def test_render_is_blocked_until_there_is_something_to_render(self):
        self.assertFalse(self.window.render_button.isEnabled())
        self.assertIn("需要先", self.window.render_button.toolTip())

    def test_advanced_options_start_collapsed(self):
        self.assertFalse(self.window.advanced.isVisible())
        self.window.advanced_toggle.setChecked(True)
        self.assertTrue(self.window.advanced.isVisible())

    def test_progress_and_cancel_are_hidden_when_idle(self):
        self.assertFalse(self.window.progress.isVisible())
        self.assertFalse(self.window.cancel_button.isVisible())


class TestLoading(WindowCase):
    def test_vehicles_appear_in_the_table(self):
        summary = self.load()
        self.assertEqual(summary.vehicle_count, 4)
        self.assertEqual(self.window.model.rowCount(), 4)
        self.assertEqual(
            self.window.model.all_ids(), ["1", "2", "3", "4"]
        )

    def test_render_becomes_available_once_a_vehicle_is_chosen(self):
        self.load()
        self.assertFalse(self.window.render_button.isEnabled())
        self.window.model.set_checked(["1"])
        self.assertTrue(self.window.render_button.isEnabled())

    def test_frame_controls_span_the_video(self):
        self.load()
        self.assertEqual(self.window.frame_spin.maximum(), FRAMES - 1)


class TestSelection(WindowCase):
    def setUp(self):
        super().setUp()
        self.load()

    def test_checking_a_row_assigns_a_colour(self):
        self.window.model.set_checked(["2"])
        color = self.window.model.index(1, 0).data(
            Qt.ItemDataRole.DecorationRole
        )
        self.assertIsNotNone(color, "選取的車輛要在清單上看得到顏色")

    def test_unselected_rows_have_no_colour(self):
        self.window.model.set_checked(["1"])
        self.assertIsNone(
            self.window.model.index(3, 0).data(Qt.ItemDataRole.DecorationRole)
        )

    def test_selection_count_is_shown(self):
        self.window.model.set_checked(["1", "2"])
        self.assertIn("2", self.window.selection_label.text())

    def test_typed_ids_select_rows(self):
        self.window.id_edit.setText("1,3")
        self.window._apply_typed_ids()
        self.assertEqual(self.window.model.selected_ids(), ["1", "3"])

    def test_unknown_typed_ids_are_reported_not_silently_dropped(self):
        self.window.id_edit.setText("1,999")
        self.window._apply_typed_ids()
        self.assertEqual(self.window.model.selected_ids(), ["1"])
        self.assertIn("999", self.window.statusBar().currentMessage())

    def test_selection_order_follows_the_table_not_the_typing(self):
        # 配色依這個順序，所以順序必須穩定可預期。
        self.window.id_edit.setText("3,1")
        self.window._apply_typed_ids()
        self.assertEqual(self.window.model.selected_ids(), ["1", "3"])

    def test_clear_removes_everything(self):
        self.window.model.set_checked(["1", "2"])
        self.window.model.clear_selection()
        self.assertEqual(self.window.model.selected_ids(), [])


class TestFiltering(WindowCase):
    def setUp(self):
        super().setUp()
        self.load()

    def shown_rows(self):
        return [row for row in range(self.window.model.rowCount())
                if not self.window.table.isRowHidden(row)]

    def test_everything_is_shown_by_default(self):
        self.assertEqual(len(self.shown_rows()), 4)

    def test_search_matches_the_vehicle_id(self):
        self.window.search_edit.setText("2")
        self.assertEqual(self.shown_rows(), [1])

    def test_search_is_a_plain_substring_match(self):
        # "B→" 會同時命中 B→A 與行穿線的 AB→AB，這是子字串比對的必然
        # 結果。要只留一般路口代號得搭配「隱藏行穿線」。
        self.window.search_edit.setText("B→")
        self.assertEqual(self.shown_rows(), [0, 2])

        self.window.hide_crosswalk.setChecked(True)
        self.assertEqual(self.shown_rows(), [0])

    def test_class_filter(self):
        index = self.window.class_filter.findData("m")
        self.window.class_filter.setCurrentIndex(index)
        self.assertEqual(len(self.shown_rows()), 2)

    def test_complete_only_hides_the_x_track(self):
        self.window.complete_only.setChecked(True)
        self.assertNotIn(3, self.shown_rows())

    def test_hiding_crosswalks(self):
        self.window.hide_crosswalk.setChecked(True)
        self.assertNotIn(2, self.shown_rows())

    def test_select_shown_only_touches_visible_rows(self):
        self.window.complete_only.setChecked(True)
        self.window._select_shown()
        self.assertNotIn("4", self.window.model.selected_ids())

    def test_filtering_does_not_change_the_selection(self):
        # 篩選是「看什麼」，不是「選什麼」——藏起來不代表取消勾選。
        self.window.model.set_checked(["4"])
        self.window.complete_only.setChecked(True)
        self.assertEqual(self.window.model.selected_ids(), ["4"])


class TestSettings(WindowCase):
    def setUp(self):
        super().setUp()
        self.load()

    def test_appearance_reads_every_control(self):
        self.window.label_combo.setCurrentIndex(
            self.window.label_combo.findData("both")
        )
        self.window.front_combo.setCurrentIndex(
            self.window.front_combo.findData("edge")
        )
        self.window.thickness_spin.setValue(4)
        self.window.fill_spin.setValue(0.3)
        self.window.gap_spin.setValue(12)
        self.window.interpolate_check.setChecked(False)
        self.window.codec_combo.setCurrentIndex(
            self.window.codec_combo.findData("mp4v")
        )

        appearance = self.window.appearance()
        self.assertEqual(appearance.label, "both")
        self.assertEqual(appearance.front, "edge")
        self.assertEqual(appearance.thickness, 4)
        self.assertAlmostEqual(appearance.fill_alpha, 0.3)
        self.assertEqual(appearance.max_gap, 12)
        self.assertFalse(appearance.interpolate)
        self.assertEqual(appearance.codec, "mp4v")

    def test_appearance_builds_a_valid_style(self):
        self.window.model.set_checked(["1", "2"])
        style = self.window.session.style_for(
            self.window.model.selected_ids(), self.window.appearance()
        )
        self.assertEqual(sorted(style.colors), ["1", "2"])

    def test_range_whole_video(self):
        self.window.range_whole.setChecked(True)
        self.assertEqual(self.window.output_range(), (0, FRAMES - 1))

    def test_range_follows_the_selection(self):
        self.window.model.set_checked(["1"])
        self.window.range_selected.setChecked(True)
        self.assertEqual(self.window.output_range(), (0, FRAMES - 1))

    def test_custom_range_enables_the_spin_boxes(self):
        self.assertFalse(self.window.start_spin.isEnabled())
        self.window.range_custom.setChecked(True)
        self.assertTrue(self.window.start_spin.isEnabled())
        self.window.start_spin.setValue(5)
        self.window.end_spin.setValue(9)
        self.assertEqual(self.window.output_range(), (5, 9))

    def test_range_with_nothing_selected_falls_back_to_the_whole_video(self):
        self.window.range_selected.setChecked(True)
        self.assertEqual(self.window.output_range(), (0, FRAMES - 1))


class TestPreview(WindowCase):
    def setUp(self):
        super().setUp()
        self.load()

    def test_preview_renders_a_frame_without_failing(self):
        self.window.model.set_checked(["1", "2"])
        self.window.frame_spin.setValue(10)
        self.window.preview._render()          # 跳過合併計時器
        self.assertIsNotNone(self.window.preview_view.pixmap())

    def test_preview_works_with_nothing_selected(self):
        self.window.frame_spin.setValue(3)
        self.window.preview._render()
        self.assertIsNotNone(self.window.preview_view.pixmap())

    def test_time_label_follows_the_frame(self):
        self.window.frame_spin.setValue(20)
        self.assertIn("2.00", self.window.time_label.text())

    def test_requests_are_coalesced(self):
        # 拖時間軸時不該每一格都解碼；合併靠一個單次計時器。
        self.window.model.set_checked(["1"])
        for frame in range(0, 10):
            self.window.frame_spin.setValue(frame)
        self.assertTrue(self.window.preview._timer.isActive())
        self.assertEqual(self.window.preview._pending[0], 9)


if __name__ == "__main__":
    unittest.main()
