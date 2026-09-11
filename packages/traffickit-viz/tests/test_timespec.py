"""時間寫法與影格編號互轉的規格測試。"""

import unittest

import pandas as pd

from traffickit_viz import frame_span, parse_time_spec, resolve_center_range

FPS = 10.0


class TestParseTimeSpec(unittest.TestCase):
    def test_plain_number_is_a_frame_number(self):
        self.assertEqual(parse_time_spec("950", FPS), 950)
        self.assertEqual(parse_time_spec(950, FPS), 950)

    def test_trailing_s_means_seconds(self):
        # 同一個 10，有沒有 s 差十倍——這是舊命令列的寫法，保留但要測清楚。
        self.assertEqual(parse_time_spec("10", FPS), 10)
        self.assertEqual(parse_time_spec("10s", FPS), 100)

    def test_clock_notation(self):
        self.assertEqual(parse_time_spec("00:01:30", FPS), 900)
        self.assertEqual(parse_time_spec("01:30", FPS), 900)
        self.assertEqual(parse_time_spec("00:00:01.5", FPS), 15)

    def test_minutes_and_seconds_may_exceed_sixty(self):
        # 人手算出來的 "0:90" 就是 90 秒，擋掉只會讓人再算一次。
        self.assertEqual(parse_time_spec("0:90", FPS), 900)

    def test_rounding_is_to_nearest_frame(self):
        self.assertEqual(parse_time_spec("0.04s", 25.0), 1)
        self.assertEqual(parse_time_spec("0.01s", 25.0), 0)

    def test_non_integer_fps_is_used_as_given(self):
        # 空拍軌跡常見的 9.99 fps：1 秒不是剛好 10 格。
        self.assertEqual(parse_time_spec("100s", 9.99), 999)

    def test_whitespace_is_trimmed(self):
        self.assertEqual(parse_time_spec("  12s  ", FPS), 120)

    def test_invalid_specs_are_rejected(self):
        cases = ["", "   ", "abc", "1:2:3:4", "12x", "1:", ":30"]
        for spec in cases:
            with self.subTest(spec=spec):
                with self.assertRaises(ValueError):
                    parse_time_spec(spec, FPS)

    def test_invalid_fps_is_rejected(self):
        for fps in (0, -1, float("inf"), float("nan")):
            with self.subTest(fps=fps):
                with self.assertRaisesRegex(ValueError, "fps"):
                    parse_time_spec("10", fps)


class TestResolveCenterRange(unittest.TestCase):
    def test_symmetric_window(self):
        self.assertEqual(resolve_center_range(100, 20, 20), (80, 120))

    def test_asymmetric_window(self):
        # 衝突事件常要多看後面的反應。
        self.assertEqual(resolve_center_range(100, 20, 40), (80, 140))

    def test_start_is_clamped_at_zero(self):
        self.assertEqual(resolve_center_range(10, 50, 10), (0, 20))

    def test_end_is_clamped_to_the_video(self):
        self.assertEqual(
            resolve_center_range(90, 10, 50, total_frames=100), (80, 99)
        )

    def test_a_centre_beyond_the_video_still_gives_a_valid_range(self):
        start, end = resolve_center_range(500, 10, 10, total_frames=100)
        self.assertLessEqual(start, end)
        self.assertLess(end, 100)

    def test_negative_lengths_count_as_zero(self):
        self.assertEqual(resolve_center_range(50, -5, -5), (50, 50))

    def test_invalid_total_frames_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "total_frames"):
            resolve_center_range(10, 1, 1, total_frames=0)


class TestFrameSpan(unittest.TestCase):
    def setUp(self):
        self.tracks = pd.DataFrame({
            "vehicle_id": ["1", "1", "2", "2"],
            "frame": [10, 20, 30, 40],
        })

    def test_span_is_the_union_of_all_vehicles(self):
        self.assertEqual(frame_span(self.tracks), (10, 40))

    def test_span_can_be_limited_to_some_vehicles(self):
        self.assertEqual(frame_span(self.tracks, vehicle_ids=["2"]), (30, 40))

    def test_padding_extends_both_ends_but_not_below_zero(self):
        self.assertEqual(frame_span(self.tracks, pad=5), (5, 45))
        self.assertEqual(frame_span(self.tracks, pad=50), (0, 90))

    def test_unknown_vehicle_gives_none(self):
        self.assertIsNone(frame_span(self.tracks, vehicle_ids=["nope"]))

    def test_empty_input_gives_none(self):
        self.assertIsNone(frame_span(self.tracks.iloc[:0]))

    def test_missing_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "缺少必要欄位"):
            frame_span(self.tracks.drop(columns=["frame"]))

    def test_negative_pad_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "負數"):
            frame_span(self.tracks, pad=-1)


if __name__ == "__main__":
    unittest.main()
