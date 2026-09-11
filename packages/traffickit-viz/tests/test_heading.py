"""車頭方向與平滑的規格測試。

期望值全部手算，並在註解寫出推導，不把實作再寫一遍當答案。
"""

import math
import unittest

import numpy as np
import pandas as pd

from traffickit_viz import add_headings


def corners(front, rear, half_width=1.0):
    """由車頭中點、車尾中點與半寬造出四個角點（車頭兩角在前）。

    只在測試裡用，刻意寫得很直白，方便人工核對。
    """
    (fx, fy), (rx, ry) = front, rear
    dx, dy = fx - rx, fy - ry
    length = math.hypot(dx, dy) or 1.0
    px, py = dy / length, -dx / length          # 垂直於車身方向
    return {
        "x1_px": fx + px * half_width, "y1_px": fy + py * half_width,
        "x2_px": fx - px * half_width, "y2_px": fy - py * half_width,
        "x3_px": rx - px * half_width, "y3_px": ry - py * half_width,
        "x4_px": rx + px * half_width, "y4_px": ry + py * half_width,
    }


def collapsed(vehicle_id, *, frame, at=(5.0, 5.0)):
    """四個角點全部重合的一列：車長為 0，算不出車身方向。"""
    x, y = at
    return pd.DataFrame([{
        "vehicle_id": vehicle_id, "frame": frame,
        **{name: (x if name.startswith("x") else y)
           for name in ("x1_px", "y1_px", "x2_px", "y2_px",
                        "x3_px", "y3_px", "x4_px", "y4_px")},
    }])


def track(vehicle_id, frames, positions):
    """positions 是 [(車頭中點, 車尾中點), ...]。"""
    return pd.DataFrame([
        {"vehicle_id": vehicle_id, "frame": frame, **corners(front, rear)}
        for frame, (front, rear) in zip(frames, positions)
    ])


# 車 1 三個影格：先朝 +x、再朝 +y、再朝 +x。
# 單格方向依序是 (1,0)、(0,1)、(1,0)。
SAMPLE = track(
    "1", [0, 1, 2],
    [((10, 0), (0, 0)), ((0, 10), (0, 0)), ((10, 0), (0, 0))],
)

ROOT_HALF = math.sqrt(2) / 2


class TestUnsmoothed(unittest.TestCase):
    def test_window_zero_gives_the_single_frame_direction(self):
        actual = add_headings(SAMPLE, window=0)
        self.assertEqual(
            [(round(x, 9), round(y, 9))
             for x, y in zip(actual["heading_x"], actual["heading_y"])],
            [(1.0, 0.0), (0.0, 1.0), (1.0, 0.0)],
        )

    def test_headings_are_unit_vectors(self):
        actual = add_headings(SAMPLE, window=0)
        lengths = np.hypot(actual["heading_x"], actual["heading_y"])
        self.assertTrue(np.allclose(lengths, 1.0))

    def test_direction_is_front_minus_rear_not_the_other_way(self):
        # 車頭在 +x 側，方向就該是 +x。搞反的話箭頭會指向車尾。
        actual = add_headings(SAMPLE, window=0)
        self.assertAlmostEqual(actual["heading_x"].iloc[0], 1.0)


class TestSmoothing(unittest.TestCase):
    def test_hand_calculated_window_of_one(self):
        # 三格的單位方向是 (1,0)、(0,1)、(1,0)。window=1 時：
        #   第 0 格取 [0,1]   → 平均 (1/2, 1/2)      → 正規化 (√2/2, √2/2)
        #   第 1 格取 [0,1,2] → 平均 (2/3, 1/3)      → 正規化 (2,1)/√5
        #   第 2 格取 [1,2]   → 平均 (1/2, 1/2)      → 正規化 (√2/2, √2/2)
        actual = add_headings(SAMPLE, window=1)
        expected = [
            (ROOT_HALF, ROOT_HALF),
            (2 / math.sqrt(5), 1 / math.sqrt(5)),
            (ROOT_HALF, ROOT_HALF),
        ]
        for row, (x, y) in enumerate(expected):
            with self.subTest(row=row):
                self.assertAlmostEqual(actual["heading_x"].iloc[row], x)
                self.assertAlmostEqual(actual["heading_y"].iloc[row], y)

    def test_smoothing_reduces_frame_to_frame_change(self):
        # 平滑的目的就是讓箭頭別晃；沒有變穩就沒有做的意義。
        rough = add_headings(SAMPLE, window=0)
        smooth = add_headings(SAMPLE, window=1)
        spread = lambda frame: float(
            np.abs(np.diff(frame["heading_x"].to_numpy())).sum()
        )
        self.assertLess(spread(smooth), spread(rough))

    def test_window_larger_than_the_track_is_fine(self):
        actual = add_headings(SAMPLE, window=99)
        # 三格全部平均：((1,0)+(0,1)+(1,0))/3 = (2/3, 1/3)
        self.assertAlmostEqual(actual["heading_x"].iloc[0], 2 / math.sqrt(5))


class TestUndefinedDirections(unittest.TestCase):
    def test_coincident_front_and_rear_gives_nan_not_zero(self):
        # 0 會被畫成「朝右」，那是假的方向；未定義就回 NaN。
        actual = add_headings(collapsed("1", frame=0), window=0)
        self.assertTrue(np.isnan(actual["heading_x"].iloc[0]))

    def test_degenerate_frames_are_skipped_not_averaged_in(self):
        frames = pd.concat([
            track("1", [0], [((10, 0), (0, 0))]),
            collapsed("1", frame=1),
        ], ignore_index=True)
        actual = add_headings(frames, window=1)
        # 只有一格有方向，平均就是那一格，不會被 0 拉短或拉偏。
        self.assertAlmostEqual(actual["heading_x"].iloc[0], 1.0)
        self.assertAlmostEqual(actual["heading_y"].iloc[0], 0.0)

    def test_opposite_directions_cancelling_out_give_nan(self):
        opposed = track(
            "1", [0, 1], [((10, 0), (0, 0)), ((0, 0), (10, 0))]
        )
        actual = add_headings(opposed, window=1)
        # (1,0) 與 (-1,0) 平均為 0，方向沒有意義。
        self.assertTrue(np.isnan(actual["heading_x"].iloc[0]))


class TestContract(unittest.TestCase):
    def test_input_is_not_modified(self):
        before = SAMPLE.copy()
        add_headings(SAMPLE)
        pd.testing.assert_frame_equal(SAMPLE, before)

    def test_row_order_is_preserved(self):
        shuffled = SAMPLE.iloc[[2, 0, 1]]
        actual = add_headings(shuffled, window=0)
        self.assertEqual(actual["frame"].tolist(), [2, 0, 1])
        # 第 1 格（朝 +y）不管排在第幾列，方向都一樣。
        row = actual.loc[actual["frame"] == 1]
        self.assertAlmostEqual(row["heading_y"].item(), 1.0)

    def test_duplicate_index_is_tolerated(self):
        repeated = SAMPLE.set_axis([0, 0, 0])
        actual = add_headings(repeated, window=0)
        self.assertEqual(len(actual), 3)

    def test_vehicles_are_smoothed_independently(self):
        two = pd.concat([
            SAMPLE,
            track("2", [0, 1, 2],
                  [((0, -10), (0, 0))] * 3),   # 整段朝 -y
        ], ignore_index=True)
        actual = add_headings(two, window=1)
        second = actual.query("vehicle_id == '2'")
        self.assertTrue(np.allclose(second["heading_y"], -1.0))
        self.assertTrue(np.allclose(second["heading_x"], 0.0, atol=1e-12))

    def test_order_by_can_be_a_time_column(self):
        by_time = SAMPLE.rename(columns={"frame": "time_s"})
        actual = add_headings(by_time, window=1, order_by="time_s")
        self.assertAlmostEqual(actual["heading_x"].iloc[0], ROOT_HALF)

    def test_empty_input_keeps_the_schema(self):
        actual = add_headings(SAMPLE.iloc[:0])
        self.assertEqual(len(actual), 0)
        self.assertIn("heading_x", actual.columns)
        self.assertIn("heading_y", actual.columns)

    def test_missing_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "缺少必要欄位"):
            add_headings(SAMPLE.drop(columns=["x1_px"]))

    def test_missing_order_column_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "缺少必要欄位"):
            add_headings(SAMPLE, order_by="nope")

    def test_invalid_window_is_rejected(self):
        for window, message in [(-1, "負數"), (1.5, "整數")]:
            with self.subTest(window=window):
                with self.assertRaisesRegex(ValueError, message):
                    add_headings(SAMPLE, window=window)

    def test_wrong_type_raises_type_error(self):
        with self.assertRaises(TypeError):
            add_headings([1, 2, 3])


if __name__ == "__main__":
    unittest.main()
