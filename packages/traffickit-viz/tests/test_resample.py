"""軌跡重新取樣的規格測試。

期望值手算：框在兩個取樣點之間等速移動，中間的影格就是線性內插。
"""

import unittest

import pandas as pd

from traffickit_viz import resample_tracks


def square(left, top=0.0, size=10.0):
    """一個軸對齊的方框，車頭兩角在左側。"""
    return {
        "x1_px": left, "y1_px": top,
        "x2_px": left, "y2_px": top + size,
        "x3_px": left + size, "y3_px": top + size,
        "x4_px": left + size, "y4_px": top,
    }


# 車 1：frame 0 在 x=0，frame 4 在 x=40，中間沒有取樣點。
SAMPLE = pd.DataFrame([
    {"vehicle_id": "1", "frame": 0, "vehicle_class": "c", **square(0.0)},
    {"vehicle_id": "1", "frame": 4, "vehicle_class": "c", **square(40.0)},
])


class TestInterpolation(unittest.TestCase):
    def test_midpoint_is_hand_calculated(self):
        # frame 0 在 x=0、frame 4 在 x=40，等速的話 frame 2 就在 x=20。
        actual = resample_tracks(SAMPLE, range(0, 5))
        middle = actual.query("frame == 2").iloc[0]
        self.assertAlmostEqual(middle["x1_px"], 20.0)
        self.assertAlmostEqual(middle["x3_px"], 30.0)
        self.assertAlmostEqual(middle["y1_px"], 0.0)

    def test_every_requested_frame_in_range_is_produced(self):
        actual = resample_tracks(SAMPLE, range(0, 5))
        self.assertEqual(actual["frame"].tolist(), [0, 1, 2, 3, 4])

    def test_sampled_frames_keep_their_original_values(self):
        actual = resample_tracks(SAMPLE, range(0, 5))
        self.assertAlmostEqual(actual.query("frame == 0")["x1_px"].item(), 0.0)
        self.assertAlmostEqual(actual.query("frame == 4")["x1_px"].item(), 40.0)

    def test_frames_outside_the_track_are_not_invented(self):
        # 車輛還沒進畫面或已經離開，不該憑空補框。
        actual = resample_tracks(SAMPLE, range(-5, 12))
        self.assertEqual(actual["frame"].min(), 0)
        self.assertEqual(actual["frame"].max(), 4)

    def test_centre_is_recomputed_from_the_interpolated_corners(self):
        actual = resample_tracks(SAMPLE, range(0, 5))
        middle = actual.query("frame == 2").iloc[0]
        self.assertAlmostEqual(middle["center_x_px"], 25.0)
        self.assertAlmostEqual(middle["center_y_px"], 5.0)

    def test_interpolation_can_be_switched_off(self):
        actual = resample_tracks(SAMPLE, range(0, 5), interpolate=False)
        self.assertEqual(actual["frame"].tolist(), [0, 4])

    def test_a_single_sample_needs_no_interpolation(self):
        one = SAMPLE.iloc[:1]
        actual = resample_tracks(one, range(0, 5))
        self.assertEqual(actual["frame"].tolist(), [0])


class TestMaxGap(unittest.TestCase):
    def test_a_gap_wider_than_max_gap_is_not_filled(self):
        # 車被遮蔽或離開畫面時軌跡會中斷；補起來會畫出一個憑空滑過去的框。
        actual = resample_tracks(SAMPLE, range(0, 5), max_gap=3)
        self.assertEqual(actual["frame"].tolist(), [0, 4])

    def test_a_gap_exactly_at_max_gap_is_filled(self):
        actual = resample_tracks(SAMPLE, range(0, 5), max_gap=4)
        self.assertEqual(len(actual), 5)

    def test_only_the_wide_segment_is_skipped(self):
        tracks = pd.DataFrame([
            {"vehicle_id": "1", "frame": 0, **square(0.0)},
            {"vehicle_id": "1", "frame": 2, **square(20.0)},
            {"vehicle_id": "1", "frame": 20, **square(200.0)},
        ])
        actual = resample_tracks(tracks, range(0, 21), max_gap=5)
        # 0–2 補起來，2–20 太遠不補，但 20 本身仍然保留。
        self.assertEqual(actual["frame"].tolist(), [0, 1, 2, 20])

    def test_zero_max_gap_keeps_only_exact_samples(self):
        actual = resample_tracks(SAMPLE, range(0, 5), max_gap=0)
        self.assertEqual(actual["frame"].tolist(), [0, 4])


class TestContract(unittest.TestCase):
    def test_output_columns_are_fixed(self):
        actual = resample_tracks(SAMPLE, range(0, 5))
        self.assertEqual(
            list(actual.columns),
            ["vehicle_id", "frame",
             "x1_px", "y1_px", "x2_px", "y2_px", "x3_px", "y3_px",
             "x4_px", "y4_px", "center_x_px", "center_y_px", "vehicle_class"],
        )

    def test_per_vehicle_columns_are_carried_over(self):
        actual = resample_tracks(SAMPLE, range(0, 5))
        self.assertEqual(actual["vehicle_class"].unique().tolist(), ["c"])

    def test_time_and_heading_columns_are_dropped(self):
        # 內插後的時間要由影片幀率決定，方向要重新正規化——沿用會是錯的。
        noisy = SAMPLE.assign(time_s=[0.0, 0.4], heading_x=1.0, heading_y=0.0)
        actual = resample_tracks(noisy, range(0, 5))
        for name in ("time_s", "heading_x", "heading_y"):
            self.assertNotIn(name, actual.columns)

    def test_a_column_that_varies_within_a_vehicle_is_rejected(self):
        # 沿用第一個值會靜靜產生錯資料，不如直接說不知道要用哪個。
        varying = SAMPLE.assign(vehicle_class=["c", "m"])
        with self.assertRaisesRegex(ValueError, "有多個值"):
            resample_tracks(varying, range(0, 5))

    def test_vehicles_are_resampled_independently(self):
        two = pd.concat([
            SAMPLE,
            pd.DataFrame([
                {"vehicle_id": "2", "frame": 2, "vehicle_class": "m",
                 **square(100.0)},
                {"vehicle_id": "2", "frame": 3, "vehicle_class": "m",
                 **square(110.0)},
            ]),
        ], ignore_index=True)
        actual = resample_tracks(two, range(0, 5))
        self.assertEqual(
            actual.query("vehicle_id == '2'")["frame"].tolist(), [2, 3]
        )

    def test_rows_are_sorted_by_vehicle_then_frame(self):
        shuffled = SAMPLE.iloc[::-1]
        actual = resample_tracks(shuffled, range(0, 5))
        self.assertEqual(actual["frame"].tolist(), [0, 1, 2, 3, 4])

    def test_input_is_not_modified(self):
        before = SAMPLE.copy()
        resample_tracks(SAMPLE, range(0, 5))
        pd.testing.assert_frame_equal(SAMPLE, before)

    def test_no_requested_frames_gives_an_empty_table_with_the_schema(self):
        actual = resample_tracks(SAMPLE, [])
        self.assertEqual(len(actual), 0)
        self.assertIn("center_x_px", actual.columns)

    def test_empty_input_gives_an_empty_table(self):
        actual = resample_tracks(SAMPLE.iloc[:0], range(0, 5))
        self.assertEqual(len(actual), 0)

    def test_missing_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "缺少必要欄位"):
            resample_tracks(SAMPLE.drop(columns=["frame"]), range(0, 5))

    def test_negative_max_gap_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "負數"):
            resample_tracks(SAMPLE, range(0, 5), max_gap=-1)

    def test_wrong_type_raises_type_error(self):
        with self.assertRaises(TypeError):
            resample_tracks([1, 2, 3], range(0, 5))


if __name__ == "__main__":
    unittest.main()
