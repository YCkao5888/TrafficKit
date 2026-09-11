"""介面背後那一層的規格測試。

這一層刻意不依賴 Qt，所以這份測試不需要建立任何視窗，也不需要
offscreen 平台——介面能不能開跟這裡算得對不對是兩件事。
"""

import tempfile
import unittest
from pathlib import Path

from traffickit_viz.gui._session import (
    Appearance,
    Session,
    parse_id_list,
    summarise_id_list,
)


def points(*values):
    return ",".join(str(value) for value in values)


def box(left, top=0, size=10):
    """一個方框，車頭兩角在左側。"""
    return points(left, top, left, top + size,
                  left + size, top + size, left + size, top)


# 車 1：frame 0–4，每格往右 10；車 2：只有 frame 0，行人走行穿線；
# 車 3：frame 0–1，進入代號 X（不完整）。
SAMPLE = [
    "1,0,4,BI,AO,c," + ",".join(box(index * 10) for index in range(5)),
    "2,0,0,AB,AB,p," + box(100, size=4),
    "3,0,1,X,CO,m," + ",".join(box(200 + index * 5) for index in range(2)),
]


class SessionCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sample_CSV_SU.csv"
        self.path.write_text("\n".join(SAMPLE) + "\n", encoding="utf-8")
        self.session = Session()
        self.summary = self.session.load_tracks(self.path)


class TestLoad(SessionCase):
    def test_summary_counts(self):
        self.assertEqual(self.summary.vehicle_count, 3)
        self.assertEqual(self.summary.incomplete_count, 1)
        self.assertEqual(self.summary.crosswalk_count, 1)
        self.assertEqual((self.summary.first_frame, self.summary.last_frame), (0, 4))

    def test_summary_text_mentions_the_important_numbers(self):
        text = self.summary.describe()
        for part in ("3 台車", "不完整 1", "行穿線 1"):
            self.assertIn(part, text)

    def test_vehicle_class_is_joined_onto_the_per_frame_table(self):
        # 車種只存在於 *_vehicles 那張表，但標籤要顯示它。
        self.assertIn("vehicle_class", self.session.tracks.columns)
        row = self.session.tracks.query("vehicle_id == '1'").iloc[0]
        self.assertEqual(row["vehicle_class"], "c")

    def test_not_ready_until_a_video_is_loaded_too(self):
        self.assertFalse(self.session.is_ready)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            Session().load_tracks(self.path.with_name("nope.csv"))


class TestBoxesForFrame(SessionCase):
    def test_a_sampled_frame_is_returned_as_is(self):
        boxes = self.session.boxes_for_frame(2, ["1"], Appearance())
        self.assertEqual(len(boxes), 1)
        self.assertAlmostEqual(boxes["x1_px"].item(), 20.0)

    def test_headings_are_present_for_the_arrow_marker(self):
        boxes = self.session.boxes_for_frame(2, ["1"], Appearance(front="arrow"))
        self.assertIn("heading_x", boxes.columns)
        # 車頭在左側、往右移動⋯⋯角點順序決定方向，這裡只確認算得出來。
        self.assertFalse(boxes["heading_x"].isna().all())

    def test_only_the_requested_vehicles_come_back(self):
        boxes = self.session.boxes_for_frame(0, ["2"], Appearance())
        self.assertEqual(boxes["vehicle_id"].tolist(), ["2"])

    def test_no_selection_gives_nothing(self):
        self.assertTrue(self.session.boxes_for_frame(0, [], Appearance()).empty)

    def test_a_frame_outside_every_track_gives_nothing(self):
        self.assertTrue(
            self.session.boxes_for_frame(99, ["1"], Appearance()).empty
        )

    def test_the_window_around_the_frame_does_not_leak_other_frames(self):
        # 取框時會多切前後幾格來算平滑，但回傳的必須只有那一格。
        boxes = self.session.boxes_for_frame(
            2, ["1"], Appearance(heading_window=5)
        )
        self.assertEqual(boxes["frame"].unique().tolist(), [2])

    def test_smoothing_window_does_not_change_the_position(self):
        rough = self.session.boxes_for_frame(2, ["1"], Appearance(heading_window=0))
        smooth = self.session.boxes_for_frame(2, ["1"], Appearance(heading_window=5))
        self.assertAlmostEqual(rough["x1_px"].item(), smooth["x1_px"].item())


class TestAppearance(unittest.TestCase):
    def test_replace_returns_a_new_instance(self):
        base = Appearance()
        changed = base.replace(thickness=5)
        self.assertEqual(base.thickness, 2)
        self.assertEqual(changed.thickness, 5)

    def test_defaults_are_sensible_for_a_first_run(self):
        appearance = Appearance()
        self.assertEqual(appearance.label, "id")
        self.assertEqual(appearance.front, "arrow")
        self.assertTrue(appearance.interpolate)


class TestIdList(unittest.TestCase):
    def test_plain_list(self):
        self.assertEqual(parse_id_list("2,4,5"), ["2", "4", "5"])

    def test_spaces_work_too(self):
        self.assertEqual(parse_id_list("2 4  5"), ["2", "4", "5"])

    def test_ranges_are_expanded(self):
        self.assertEqual(parse_id_list("10-13"), ["10", "11", "12", "13"])

    def test_reversed_range_is_tolerated(self):
        self.assertEqual(parse_id_list("13-10"), ["10", "11", "12", "13"])

    def test_mixed_notation(self):
        self.assertEqual(parse_id_list("2,4-6"), ["2", "4", "5", "6"])

    def test_duplicates_collapse_keeping_the_first_position(self):
        self.assertEqual(parse_id_list("5,2,5"), ["5", "2"])

    def test_non_numeric_ids_are_kept_verbatim(self):
        # 範圍寫法只在數字 ID 上有意義，別把 'a-b' 拆掉。
        self.assertEqual(parse_id_list("a-b,7"), ["a-b", "7"])

    def test_empty_input(self):
        self.assertEqual(parse_id_list(""), [])

    def test_summary_is_the_inverse_for_runs(self):
        self.assertEqual(
            summarise_id_list(["2", "4", "5", "10", "11", "12"]), "2,4,5,10-12"
        )

    def test_summary_only_abbreviates_runs_of_three_or_more(self):
        self.assertEqual(summarise_id_list(["1", "2"]), "1,2")
        self.assertEqual(summarise_id_list(["1", "2", "3"]), "1-3")

    def test_round_trip(self):
        for text in ("2,4,5,10-12", "1-3", "7"):
            with self.subTest(text=text):
                self.assertEqual(summarise_id_list(parse_id_list(text)), text)


if __name__ == "__main__":
    unittest.main()
