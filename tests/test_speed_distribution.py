"""車速分布統計的規格測試。

測試驗證契約中的交通定義與資料品質政策，不重寫一遍算法當作預期答案。
資料與手算答案見 docs/worksheets/speed.speed_distribution.md。
"""

import math
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from traffickit.speed import (
    SpeedDistribution,
    speed_bin_edges,
    summarise_speed_distribution,
)

EDGES = (0.0, 5.0, 10.0, 15.0)

BIN_DTYPES = {
    "bin_index": "int64",
    "lower_mps": "float64",
    "upper_mps": "float64",
    "vehicle_count": "int64",
    "proportion": "float64",
}

VEHICLE_DTYPES = {
    "vehicle_id": "string",
    "sample_count": "int64",
    "speed_mps": "float64",
}


def expected_bins(counts, proportions, edges=EDGES) -> pd.DataFrame:
    return pd.DataFrame({
        "bin_index": list(range(len(counts))),
        "lower_mps": list(edges[:-1]),
        "upper_mps": list(edges[1:]),
        "vehicle_count": list(counts),
        "proportion": list(proportions),
    }).astype(BIN_DTYPES)


class TestSpeedDistribution(unittest.TestCase):
    def setUp(self):
        # A 平均 9、B 平均 32/3、C 平均 31/3、D 平均 1（慢速車）。
        self.tracks = pd.DataFrame({
            "vehicle_id": ["A"] * 3 + ["B"] * 3 + ["C"] * 3 + ["D"] * 2,
            "time_s": [0.0, 1.0, 2.0] * 3 + [0.0, 1.0],
            "speed_smooth_mps": [
                8.0, 9.0, 10.0,
                9.0, 11.0, 12.0,
                11.0, 11.0, 9.0,
                0.5, 1.5,
            ],
        })

    def test_hand_calculated_bins_and_vehicle_speeds(self):
        result = summarise_speed_distribution(
            self.tracks, bin_edges_mps=EDGES, statistic="mean"
        )
        assert_frame_equal(
            result.bins,
            expected_bins([1, 1, 2], [0.25, 0.25, 0.5]),
        )
        expected_speeds = pd.DataFrame({
            "vehicle_id": ["A", "B", "C", "D"],
            "sample_count": [3, 3, 3, 2],
            "speed_mps": [9.0, 32 / 3, 31 / 3, 1.0],
        }).astype(VEHICLE_DTYPES)
        assert_frame_equal(result.vehicle_speeds, expected_speeds)
        self.assertEqual(result.statistic, "mean")
        self.assertIsNone(result.moving_threshold_mps)
        self.assertEqual(result.input_vehicle_count, 4)
        self.assertEqual(result.binned_vehicle_count, 4)
        self.assertEqual(result.below_range_count, 0)
        self.assertEqual(result.above_range_count, 0)

    def test_summary_matches_hand_calculation(self):
        summary = summarise_speed_distribution(
            self.tracks, bin_edges_mps=EDGES, statistic="mean"
        ).summary
        self.assertEqual(summary.vehicle_count, 4)
        self.assertAlmostEqual(summary.mean_mps, 31 / 4)
        self.assertAlmostEqual(summary.min_mps, 1.0)
        self.assertAlmostEqual(summary.max_mps, 32 / 3)
        self.assertAlmostEqual(summary.median_mps, 29 / 3)
        # 線性內插：位置 0.85 * 3 = 2.55，落在 31/3 與 32/3 之間。
        self.assertAlmostEqual(summary.p85_mps, 31.55 / 3)
        # 離差平方和 = 8972/144，除以 (n - 1) = 3 後開根號。
        self.assertAlmostEqual(summary.std_mps, math.sqrt(2243 / 108))

    def test_each_statistic_selects_expected_vehicle_speed(self):
        cases = {
            "mean": [9.0, 32 / 3, 31 / 3, 1.0],
            "median": [9.0, 11.0, 11.0, 1.0],
            "max": [10.0, 12.0, 11.0, 1.5],
            "p85": [9.7, 11.7, 11.0, 1.35],
        }
        for statistic, expected in cases.items():
            with self.subTest(statistic=statistic):
                result = summarise_speed_distribution(
                    self.tracks, bin_edges_mps=EDGES, statistic=statistic
                )
                for actual, wanted in zip(
                    result.vehicle_speeds["speed_mps"], expected
                ):
                    self.assertAlmostEqual(actual, wanted)

    def test_last_bin_includes_its_upper_edge(self):
        # A 的最大值剛好等於最後一個邊界 10，應落在最後一箱。
        edges = (0.0, 5.0, 10.0)
        result = summarise_speed_distribution(
            self.tracks, bin_edges_mps=edges, statistic="max"
        )
        assert_frame_equal(
            result.bins,
            expected_bins([1, 1], [0.5, 0.5], edges=edges),
        )
        self.assertEqual(result.binned_vehicle_count, 2)
        self.assertEqual(result.above_range_count, 2)

    def test_out_of_range_vehicles_are_counted_not_dropped(self):
        edges = (5.0, 10.0)
        result = summarise_speed_distribution(
            self.tracks, bin_edges_mps=edges, statistic="mean"
        )
        assert_frame_equal(
            result.bins,
            expected_bins([1], [1.0], edges=edges),
        )
        self.assertEqual(result.below_range_count, 1)
        self.assertEqual(result.above_range_count, 2)
        self.assertEqual(result.binned_vehicle_count, 1)
        # 統計母體仍是全部四台車，不因分箱範圍而改變。
        self.assertEqual(result.summary.vehicle_count, 4)

    def test_moving_threshold_removes_whole_vehicle(self):
        result = summarise_speed_distribution(
            self.tracks,
            bin_edges_mps=EDGES,
            statistic="mean",
            moving_threshold_mps=2.0,
        )
        self.assertEqual(result.input_vehicle_count, 4)
        self.assertEqual(result.summary.vehicle_count, 3)
        self.assertEqual(
            result.vehicle_speeds["vehicle_id"].tolist(), ["A", "B", "C"]
        )
        assert_frame_equal(
            result.bins,
            expected_bins([0, 1, 2], [0.0, 1 / 3, 2 / 3]),
        )

    def test_threshold_is_strict_and_applies_per_sample(self):
        # 門檻 9.0：A 只剩 10、C 只剩 11 與 11，B 剩 11 與 12。
        result = summarise_speed_distribution(
            self.tracks,
            bin_edges_mps=EDGES,
            statistic="mean",
            moving_threshold_mps=9.0,
        )
        expected_speeds = pd.DataFrame({
            "vehicle_id": ["A", "B", "C"],
            "sample_count": [1, 2, 2],
            "speed_mps": [10.0, 11.5, 11.0],
        }).astype(VEHICLE_DTYPES)
        assert_frame_equal(result.vehicle_speeds, expected_speeds)

    def test_unsorted_rows_duplicate_index_and_no_mutation(self):
        shuffled = self.tracks.sample(frac=1, random_state=7).copy()
        shuffled.index = [0] * len(shuffled)
        before = shuffled.copy(deep=True)
        actual = summarise_speed_distribution(shuffled, bin_edges_mps=EDGES)
        expected = summarise_speed_distribution(
            self.tracks, bin_edges_mps=EDGES
        )
        assert_frame_equal(actual.bins, expected.bins)
        assert_frame_equal(actual.vehicle_speeds, expected.vehicle_speeds)
        assert_frame_equal(shuffled, before)

    def test_extra_columns_are_ignored(self):
        with_extra = self.tracks.assign(
            vehicle_class=["car"] * 9 + ["motorcycle"] * 2
        )
        actual = summarise_speed_distribution(with_extra, bin_edges_mps=EDGES)
        expected = summarise_speed_distribution(
            self.tracks, bin_edges_mps=EDGES
        )
        assert_frame_equal(actual.vehicle_speeds, expected.vehicle_speeds)
        self.assertEqual(
            list(actual.vehicle_speeds.columns),
            ["vehicle_id", "sample_count", "speed_mps"],
        )

    def test_empty_input_and_all_filtered_share_one_schema(self):
        from_empty = summarise_speed_distribution(
            self.tracks.iloc[:0], bin_edges_mps=EDGES
        )
        from_filtered = summarise_speed_distribution(
            self.tracks, bin_edges_mps=EDGES, moving_threshold_mps=100.0
        )
        assert_frame_equal(from_empty.bins, from_filtered.bins)
        assert_frame_equal(
            from_empty.vehicle_speeds, from_filtered.vehicle_speeds
        )
        assert_frame_equal(
            from_empty.bins, expected_bins([0, 0, 0], [0.0, 0.0, 0.0])
        )
        self.assertEqual(
            [str(dtype) for dtype in from_empty.vehicle_speeds.dtypes],
            ["string", "int64", "float64"],
        )
        self.assertEqual(from_empty.summary.vehicle_count, 0)
        self.assertIsNone(from_empty.summary.mean_mps)
        self.assertIsNone(from_empty.summary.p85_mps)
        # 門檻前後的車輛數不同，分母仍分別可讀。
        self.assertEqual(from_empty.input_vehicle_count, 0)
        self.assertEqual(from_filtered.input_vehicle_count, 4)

    def test_single_vehicle_std_is_none_not_zero(self):
        one_vehicle = self.tracks[self.tracks["vehicle_id"] == "A"]
        summary = summarise_speed_distribution(
            one_vehicle, bin_edges_mps=EDGES
        ).summary
        self.assertEqual(summary.vehicle_count, 1)
        self.assertAlmostEqual(summary.mean_mps, 9.0)
        self.assertIsNone(summary.std_mps)

    def test_result_object_is_frozen(self):
        result = summarise_speed_distribution(self.tracks, bin_edges_mps=EDGES)
        self.assertIsInstance(result, SpeedDistribution)
        with self.assertRaises(Exception):
            result.statistic = "max"

    def test_non_dataframe_is_rejected(self):
        with self.assertRaises(TypeError):
            summarise_speed_distribution(
                [{"vehicle_id": "A"}], bin_edges_mps=EDGES
            )

    def test_missing_column_is_reported(self):
        invalid = self.tracks.drop(columns="speed_smooth_mps")
        with self.assertRaisesRegex(ValueError, "缺少必要欄位"):
            summarise_speed_distribution(invalid, bin_edges_mps=EDGES)

    def test_bad_speed_values_are_rejected(self):
        for value in [float("nan"), float("inf"), -1.0]:
            with self.subTest(value=value):
                invalid = self.tracks.copy()
                invalid.loc[0, "speed_smooth_mps"] = value
                with self.assertRaisesRegex(ValueError, "speed_smooth_mps"):
                    summarise_speed_distribution(invalid, bin_edges_mps=EDGES)
        invalid = self.tracks.astype({"speed_smooth_mps": "string"})
        with self.assertRaisesRegex(ValueError, "speed_smooth_mps"):
            summarise_speed_distribution(invalid, bin_edges_mps=EDGES)

    def test_invalid_id_and_time_are_rejected(self):
        for column, value in [("vehicle_id", "  "), ("time_s", -1.0)]:
            with self.subTest(column=column):
                invalid = self.tracks.copy()
                invalid.loc[0, column] = value
                with self.assertRaisesRegex(ValueError, column):
                    summarise_speed_distribution(invalid, bin_edges_mps=EDGES)

    def test_duplicate_sample_is_rejected(self):
        invalid = pd.concat([self.tracks, self.tracks.iloc[[0]]])
        with self.assertRaisesRegex(ValueError, "重複樣本"):
            summarise_speed_distribution(invalid, bin_edges_mps=EDGES)

    def test_invalid_statistic_is_rejected(self):
        for value in ["q85", "avg", "", None]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "statistic"):
                    summarise_speed_distribution(
                        self.tracks, bin_edges_mps=EDGES, statistic=value
                    )

    def test_invalid_bin_edges_are_rejected(self):
        for value in [
            (5.0,),
            (),
            (0.0, 5.0, 5.0),
            (0.0, 10.0, 5.0),
            (-1.0, 5.0),
            (0.0, float("inf")),
            (0.0, float("nan")),
            (0.0, "5"),
            "0,5",
            5.0,
        ]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "bin_edges_mps"):
                    summarise_speed_distribution(
                        self.tracks, bin_edges_mps=value
                    )

    def test_invalid_moving_threshold_is_rejected(self):
        for value in [True, "2", -1.0, float("nan"), float("inf")]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "moving_threshold_mps"):
                    summarise_speed_distribution(
                        self.tracks,
                        bin_edges_mps=EDGES,
                        moving_threshold_mps=value,
                    )


class TestSpeedBinEdges(unittest.TestCase):
    def test_edges_cover_the_requested_upper_bound(self):
        self.assertEqual(
            speed_bin_edges(5.0, 15.0), (0.0, 5.0, 10.0, 15.0)
        )
        self.assertEqual(
            speed_bin_edges(5.0, 12.0), (0.0, 5.0, 10.0, 15.0)
        )
        self.assertEqual(
            speed_bin_edges(3.0, 8.0, start_mps=2.0), (2.0, 5.0, 8.0)
        )

    def test_degenerate_span_still_returns_one_bin(self):
        self.assertEqual(speed_bin_edges(5.0, 0.0), (0.0, 5.0))

    def test_float_accumulation_does_not_leak_into_edges(self):
        self.assertEqual(
            speed_bin_edges(0.1, 0.5), (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
        )

    def test_invalid_arguments_are_rejected(self):
        cases = [
            ("width_mps", (0.0, 10.0), {}),
            ("width_mps", (-1.0, 10.0), {}),
            ("width_mps", (float("nan"), 10.0), {}),
            ("upper_mps", (5.0, -1.0), {}),
            ("upper_mps", (5.0, 1.0), {"start_mps": 2.0}),
            ("start_mps", (5.0, 10.0), {"start_mps": -1.0}),
            ("width_mps", (True, 10.0), {}),
        ]
        for name, args, kwargs in cases:
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, name):
                    speed_bin_edges(*args, **kwargs)


if __name__ == "__main__":
    unittest.main()
