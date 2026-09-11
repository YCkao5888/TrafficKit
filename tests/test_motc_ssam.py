"""MOTC_SSAM 軌跡檔讀取的規格測試。

測試驗證格式契約與資料品質政策，不重寫一遍剖析器當作預期答案。
資料與手算答案見 docs/worksheets/formats.motc_ssam.md。
"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from traffickit.formats import (
    INCOMPLETE_CODE,
    read_motc_ssam_tracks,
    read_motc_ssam_vehicles,
)
from traffickit.volume import (
    DEFAULT_PCU_WEIGHTS,
    clockwise_movements,
    summarise_turn_volume,
)

HEADER = (
    "Timestep,Vehicle ID,Link ID,Lane ID,Front X,Front Y,Rear X,Rear Y,"
    "Length,Width,Speed,class,intersection in,intersection out"
)

PREAMBLE = [
    "FORMAT,SSAM Trajectory",
    "DIMENSIONS,Scale,1,MaxX,1000,MaxY,1000",
]

# 車 1：兩個時間步，車頭朝 +x，B 進 A 出的汽車。
# 車 2：一個時間步，車頭朝 -y，A 進 C 出的機車。
# 車 3：一個時間步，行人走行穿線（AB→AB）。
# 車 4：一個時間步，進入代號 X（不完整軌跡）。
# 時間步分隔列有兩種寫法：只有 Timestep，或把逗號補滿到與表頭同寬。
# 真實檔用的是後者，兩種都要能略過。
ROWS = [
    "0.1",
    "0.1,1,1,1,10.0,5.0,6.0,5.0,4.0,2.0,10.0,c,BI,AO",
    "0.1,2,1,1,0.0,0.0,0.0,-3.0,3.0,1.5,8.0,m,AI,CO",
    "0.2,,,,,,,,,,,,,",
    "0.2,1,1,1,12.0,5.0,8.0,5.0,4.0,2.0,10.0,c,BI,AO",
    "0.2,3,1,1,20.0,20.0,19.0,20.0,1.0,0.6,1.2,p,AB,AB",
    "0.2,4,1,1,30.0,30.0,26.0,30.0,4.0,2.0,5.0,c,X,CO",
]

SAMPLE = [*PREAMBLE, HEADER, *ROWS]


class MotcSsamFileCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sample_CSV_SSAM.csv"
        self.write(SAMPLE)

    def write(self, lines, encoding="utf-8"):
        self.path.write_text("\n".join(lines) + "\n", encoding=encoding)
        return self.path


class TestReadVehicles(MotcSsamFileCase):
    def test_hand_calculated_vehicles(self):
        actual = read_motc_ssam_vehicles(self.path)
        expected = pd.DataFrame({
            "vehicle_id": ["1", "2", "3", "4"],
            "entry_gate": ["B", "A", "AB", "X"],
            "exit_gate": ["A", "C", "AB", "C"],
            "vehicle_class": ["c", "m", "p", "c"],
            "entry_time_s": [0.1, 0.1, 0.2, 0.2],
            "exit_time_s": [0.2, 0.1, 0.2, 0.2],
            "sample_count": [2, 1, 1, 1],
            "is_complete": [True, True, True, False],
            "is_crosswalk": [False, False, True, False],
        }).astype({
            "vehicle_id": "string", "entry_gate": "string",
            "exit_gate": "string", "vehicle_class": "string",
            "entry_time_s": "float64", "exit_time_s": "float64",
            "sample_count": "int64", "is_complete": "bool",
            "is_crosswalk": "bool",
        })
        assert_frame_equal(actual, expected)

    def test_gate_suffix_is_stripped_but_x_and_crosswalk_are_kept(self):
        actual = read_motc_ssam_vehicles(self.path).set_index("vehicle_id")
        self.assertEqual(actual.loc["1", "entry_gate"], "B")
        self.assertEqual(actual.loc["4", "entry_gate"], INCOMPLETE_CODE)
        self.assertEqual(actual.loc["3", "entry_gate"], "AB")

    def test_rows_are_sorted_by_entry_time_then_id(self):
        shuffled = [*PREAMBLE, HEADER, *reversed(ROWS)]
        actual = read_motc_ssam_vehicles(self.write(shuffled))
        self.assertEqual(actual["vehicle_id"].tolist(), ["1", "2", "3", "4"])
        # 打亂順序不影響每台車的起訖時間。
        self.assertEqual(actual.loc[0, "entry_time_s"], 0.1)
        self.assertEqual(actual.loc[0, "exit_time_s"], 0.2)

    def test_sample_count_matches_track_row_count(self):
        vehicles = read_motc_ssam_vehicles(self.path)
        tracks = read_motc_ssam_tracks(self.path)
        self.assertEqual(len(tracks), int(vehicles["sample_count"].sum()))

    def test_header_only_file_keeps_schema(self):
        actual = read_motc_ssam_vehicles(self.write([*PREAMBLE, HEADER]))
        self.assertEqual(len(actual), 0)
        self.assertEqual(
            [str(dtype) for dtype in actual.dtypes],
            ["string", "string", "string", "string", "float64", "float64",
             "int64", "bool", "bool"],
        )


class TestReadTracks(MotcSsamFileCase):
    def test_hand_calculated_corners(self):
        actual = read_motc_ssam_tracks(self.path).set_index(
            ["vehicle_id", "time_s"])
        # 車 1 在 0.1 秒：車頭中點 (10,5)、車尾中點 (6,5)、車寬 2。
        # 車身方向 (1,0)，垂直方向 (0,-1)，半寬 1
        # → 車頭兩角 (10,4)、(10,6)；車尾兩角 (6,6)、(6,4)。
        first = actual.loc[("1", 0.1)]
        self.assertEqual(
            [first[name] for name in
             ("x1_m", "y1_m", "x2_m", "y2_m", "x3_m", "y3_m", "x4_m", "y4_m")],
            [10.0, 4.0, 10.0, 6.0, 6.0, 6.0, 6.0, 4.0],
        )
        # 車 2 車頭朝 -y：車身方向 (0,1)、垂直方向 (1,0)、半寬 0.75。
        second = actual.loc[("2", 0.1)]
        self.assertEqual(
            [second[name] for name in ("x1_m", "y1_m", "x3_m", "y3_m")],
            [0.75, 0.0, -0.75, -3.0],
        )

    def test_centre_is_both_the_corner_mean_and_the_axle_midpoint(self):
        actual = read_motc_ssam_tracks(self.path)
        corners_x = actual[["x1_m", "x2_m", "x3_m", "x4_m"]].mean(axis=1)
        corners_y = actual[["y1_m", "y2_m", "y3_m", "y4_m"]].mean(axis=1)
        self.assertTrue((corners_x - actual["center_x_m"]).abs().max() < 1e-12)
        self.assertTrue((corners_y - actual["center_y_m"]).abs().max() < 1e-12)
        self.assertAlmostEqual(actual["center_x_m"].iloc[0], 8.0)

    def test_width_is_the_corner_separation(self):
        # 還原出來的矩形寬度必須等於檔案裡的 Width，否則角點算錯了。
        actual = read_motc_ssam_tracks(self.path).iloc[0]
        span = ((actual["x1_m"] - actual["x2_m"]) ** 2
                + (actual["y1_m"] - actual["y2_m"]) ** 2) ** 0.5
        self.assertAlmostEqual(span, actual["width_m"])

    def test_flags_are_carried_to_every_sample(self):
        actual = read_motc_ssam_tracks(self.path)
        self.assertEqual(
            actual.loc[actual["vehicle_id"] == "1", "is_complete"].tolist(),
            [True, True],
        )
        self.assertEqual(
            actual.loc[actual["vehicle_id"] == "3", "is_crosswalk"].tolist(),
            [True],
        )

    def test_rows_are_sorted_by_vehicle_then_time(self):
        shuffled = [*PREAMBLE, HEADER, *reversed(ROWS)]
        actual = read_motc_ssam_tracks(self.write(shuffled))
        self.assertEqual(
            list(zip(actual["vehicle_id"], actual["time_s"])),
            [("1", 0.1), ("1", 0.2), ("2", 0.1), ("3", 0.2), ("4", 0.2)],
        )

    def test_header_only_file_keeps_schema(self):
        actual = read_motc_ssam_tracks(self.write([*PREAMBLE, HEADER]))
        self.assertEqual(len(actual), 0)
        self.assertEqual(
            list(actual.columns),
            ["vehicle_id", "time_s",
             "front_x_m", "front_y_m", "rear_x_m", "rear_y_m",
             "length_m", "width_m",
             "x1_m", "y1_m", "x2_m", "y2_m", "x3_m", "y3_m", "x4_m", "y4_m",
             "center_x_m", "center_y_m", "is_complete", "is_crosswalk"],
        )


class TestHeaderHandling(MotcSsamFileCase):
    def test_preamble_and_blank_lines_are_skipped(self):
        lines = [*PREAMBLE, "", "   ", HEADER, "", ROWS[1]]
        self.assertEqual(len(read_motc_ssam_vehicles(self.write(lines))), 1)

    def test_both_separator_styles_are_skipped(self):
        # 真實檔的分隔列會把逗號補滿到與表頭同寬，光看欄位數判斷不出來。
        lines = [*PREAMBLE, HEADER, "0.1", "0.1,,,,,,,,,,,,,", ROWS[1]]
        actual = read_motc_ssam_vehicles(self.write(lines))
        self.assertEqual(actual["vehicle_id"].tolist(), ["1"])

    def test_header_is_matched_case_insensitively(self):
        lines = [*PREAMBLE, HEADER.upper(), ROWS[1]]
        actual = read_motc_ssam_vehicles(self.write(lines))
        self.assertEqual(actual["entry_gate"].item(), "B")

    def test_column_order_does_not_matter(self):
        # 欄位以名稱定位，不以位置定位。
        reordered_header = (
            "Timestep,class,intersection in,intersection out,Vehicle ID,"
            "Width,Length,Rear Y,Rear X,Front Y,Front X"
        )
        reordered_row = "0.1,c,BI,AO,1,2.0,4.0,5.0,6.0,5.0,10.0"
        actual = read_motc_ssam_tracks(
            self.write([*PREAMBLE, reordered_header, reordered_row]))
        self.assertEqual(actual["front_x_m"].item(), 10.0)
        self.assertEqual(actual["x1_m"].item(), 10.0)

    def test_missing_header_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "找不到.*表頭列"):
            read_motc_ssam_vehicles(self.write([*PREAMBLE, ROWS[1]]))

    def test_missing_required_column_is_rejected(self):
        without_width = HEADER.replace(",Width,", ",")
        with self.assertRaisesRegex(ValueError, "缺少必要欄位.*width"):
            read_motc_ssam_vehicles(
                self.write([*PREAMBLE, without_width, ROWS[1]]))

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_motc_ssam_vehicles(self.path.with_name("nope.csv"))

    def test_byte_order_mark_is_tolerated(self):
        self.write(SAMPLE, encoding="utf-8-sig")
        self.assertEqual(len(read_motc_ssam_vehicles(self.path)), 4)


class TestQualityPolicy(MotcSsamFileCase):
    def assert_rejects(self, row, message):
        with self.assertRaisesRegex(ValueError, message):
            read_motc_ssam_tracks(self.write([*PREAMBLE, HEADER, row]))

    def test_short_row_that_is_not_a_separator_is_rejected(self):
        self.assert_rejects("0.1,1,1,1,10.0", "只有 5 個欄位")

    def test_non_numeric_values_are_rejected(self):
        self.assert_rejects(
            "oops,1,1,1,10.0,5.0,6.0,5.0,4.0,2.0,10.0,c,BI,AO",
            "第 4 行的 Timestep 'oops' 不是數值")
        self.assert_rejects(
            "0.1,1,1,1,oops,5.0,6.0,5.0,4.0,2.0,10.0,c,BI,AO",
            "第 4 行的 front x 'oops' 不是數值")

    def test_non_finite_values_are_rejected(self):
        self.assert_rejects(
            "0.1,1,1,1,nan,5.0,6.0,5.0,4.0,2.0,10.0,c,BI,AO",
            "不是有限數值")

    def test_blank_vehicle_id_is_rejected(self):
        self.assert_rejects(
            "0.1,,1,1,10.0,5.0,6.0,5.0,4.0,2.0,10.0,c,BI,AO",
            "車輛 ID 是空白")

    def test_invalid_gate_code_is_rejected(self):
        self.assert_rejects(
            "0.1,1,1,1,10.0,5.0,6.0,5.0,4.0,2.0,10.0,c,BO,AO",
            "進入路口代號")

    def test_unknown_vehicle_class_is_rejected(self):
        self.assert_rejects(
            "0.1,1,1,1,10.0,5.0,6.0,5.0,4.0,2.0,10.0,z,BI,AO",
            "車種代號")

    def test_non_positive_width_is_rejected(self):
        self.assert_rejects(
            "0.1,1,1,1,10.0,5.0,6.0,5.0,4.0,0.0,10.0,c,BI,AO",
            "車寬 0.0 不是正數")

    def test_coincident_front_and_rear_is_rejected(self):
        # 車長 0 就決定不了車身方向，還原出來的角點會是任意方向。
        self.assert_rejects(
            "0.1,1,1,1,10.0,5.0,10.0,5.0,0.0,2.0,10.0,c,BI,AO",
            "車頭與車尾座標相同")

    def test_duplicate_vehicle_and_timestep_is_rejected(self):
        rows = [ROWS[1], ROWS[1]]
        with self.assertRaisesRegex(ValueError, "在時間 0.1 秒重複出現"):
            read_motc_ssam_vehicles(self.write([*PREAMBLE, HEADER, *rows]))

    def test_inconsistent_gate_for_one_vehicle_is_rejected(self):
        rows = [
            "0.1,1,1,1,10.0,5.0,6.0,5.0,4.0,2.0,10.0,c,BI,AO",
            "0.2,1,1,1,12.0,5.0,8.0,5.0,4.0,2.0,10.0,c,BI,CO",
        ]
        with self.assertRaisesRegex(ValueError, "駛出路口代號.*不一致"):
            read_motc_ssam_vehicles(self.write([*PREAMBLE, HEADER, *rows]))

    def test_inconsistent_class_for_one_vehicle_is_rejected(self):
        rows = [
            "0.1,1,1,1,10.0,5.0,6.0,5.0,4.0,2.0,10.0,c,BI,AO",
            "0.2,1,1,1,12.0,5.0,8.0,5.0,4.0,2.0,10.0,m,BI,AO",
        ]
        with self.assertRaisesRegex(ValueError, "車種代號.*不一致"):
            read_motc_ssam_vehicles(self.write([*PREAMBLE, HEADER, *rows]))

    def test_both_entry_points_fail_the_same_way(self):
        # 同一份壞檔案，兩個入口要以相同理由失敗，不能一個過一個不過。
        broken = [*PREAMBLE, HEADER,
                  "0.1,1,1,1,10.0,5.0,6.0,5.0,4.0,2.0,10.0,z,BI,AO"]
        self.write(broken)
        for reader in (read_motc_ssam_vehicles, read_motc_ssam_tracks):
            with self.subTest(reader=reader.__name__):
                with self.assertRaisesRegex(ValueError, "車種代號"):
                    reader(self.path)


class TestEndToEnd(MotcSsamFileCase):
    def test_file_to_turn_volume(self):
        vehicles = read_motc_ssam_vehicles(self.path)
        usable = vehicles.query("is_complete and not is_crosswalk")
        movements = clockwise_movements(
            ["A", "B", "C", "D"], disallowed=[(g, g) for g in "ABCD"]
        )
        result = summarise_turn_volume(
            usable,
            movements=movements,
            vehicle_groups={"小型車": ["c"], "機車": ["m"]},
            pcu_weights=DEFAULT_PCU_WEIGHTS,
        )
        # 車 1：B→A 是右轉的小型車；車 2：A→C 是直行的機車；
        # 車 3（行穿線）與車 4（X）被過濾掉。
        self.assertEqual(result.summary.counted_vehicle_count, 2)
        self.assertAlmostEqual(result.summary.total_pcu, 1.08 + 0.42)

    def test_unfiltered_rows_break_turn_volume(self):
        vehicles = read_motc_ssam_vehicles(self.path)
        movements = clockwise_movements(["A", "B", "C", "D"])
        with self.assertRaisesRegex(ValueError, "未定義的"):
            summarise_turn_volume(
                vehicles,
                movements=movements,
                vehicle_groups={"小型車": ["c"], "機車": ["m"]},
                pcu_weights=DEFAULT_PCU_WEIGHTS,
            )


if __name__ == "__main__":
    unittest.main()
