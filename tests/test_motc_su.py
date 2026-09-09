"""MOTC_SU 軌跡檔讀取與順時針轉向對照表的規格測試。

測試驗證格式契約與資料品質政策，不重寫一遍剖析器當作預期答案。
資料與手算答案見 docs/worksheets/formats.motc_su.md。
"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from traffickit.formats import (
    DEFAULT_FPS,
    INCOMPLETE_CODE,
    MOTC_SU_VEHICLE_CLASSES,
    read_motc_su_vehicles,
    read_motc_su_tracks,
)
from traffickit.volume import (
    DEFAULT_PCU_WEIGHTS,
    clockwise_movements,
    summarise_turn_volume,
)


def points(*values: float) -> str:
    """把一組座標值接成 CSV 片段。"""
    return ",".join(str(value) for value in values)


# 車 1：frame 0–1（兩個 frame），B 進 A 出，汽車。
# 車 2：frame 2 單一 frame，A 進 C 出，機車。
# 車 3：frame 2 單一 frame，進入代號 X（不完整）。
SAMPLE = [
    "1,0,1,BI,AO,c," + points(0, 0, 10, 0, 10, 10, 0, 10)
    + "," + points(2, 2, 12, 2, 12, 12, 2, 12),
    "2,2,2,AI,CO,m," + points(4, 6, 8, 6, 8, 10, 4, 10),
    "3,2,2,X,CO,c," + points(1, 1, 3, 1, 3, 3, 1, 3),
]


class MotcSuFileCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sample_CSV_SU.csv"
        self.write(SAMPLE)

    def write(self, lines):
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.path


class TestReadPassages(MotcSuFileCase):
    def test_hand_calculated_vehicles(self):
        actual = read_motc_su_vehicles(self.path)
        expected = pd.DataFrame({
            "vehicle_id": ["1", "2", "3"],
            "entry_gate": ["B", "A", "X"],
            "exit_gate": ["A", "C", "C"],
            "vehicle_class": ["c", "m", "c"],
            "entry_frame": [0, 2, 2],
            "exit_frame": [1, 2, 2],
            "frame_count": [2, 1, 1],
            # frame / fps，fps 預設 9.99。
            "entry_time_s": [0.0, 2 / 9.99, 2 / 9.99],
            "exit_time_s": [1 / 9.99, 2 / 9.99, 2 / 9.99],
            "is_complete": [True, True, False],
        }).astype({
            "vehicle_id": "string", "entry_gate": "string",
            "exit_gate": "string", "vehicle_class": "string",
            "entry_frame": "int64", "exit_frame": "int64",
            "frame_count": "int64", "entry_time_s": "float64",
            "exit_time_s": "float64", "is_complete": "bool",
        })
        assert_frame_equal(actual, expected)

    def test_gate_suffix_is_stripped_but_x_is_kept(self):
        actual = read_motc_su_vehicles(self.path)
        self.assertEqual(actual["entry_gate"].tolist(), ["B", "A", INCOMPLETE_CODE])
        self.assertEqual(
            actual.loc[actual["entry_gate"] == INCOMPLETE_CODE, "is_complete"].item(),
            False,
        )

    def test_fps_only_changes_seconds_not_frames(self):
        default = read_motc_su_vehicles(self.path)
        faster = read_motc_su_vehicles(self.path, fps=30.0)
        assert_frame_equal(
            default[["entry_frame", "exit_frame", "frame_count"]],
            faster[["entry_frame", "exit_frame", "frame_count"]],
        )
        self.assertAlmostEqual(faster["exit_time_s"].iloc[0], 1 / 30)
        # 9.99 = 29.97/3，實際拍攝速率；格式定義文件寫的是整數 10。
        self.assertEqual(DEFAULT_FPS, 9.99)

    def test_rows_are_sorted_by_entry_frame_then_id(self):
        shuffled = [SAMPLE[2], SAMPLE[0], SAMPLE[1]]
        actual = read_motc_su_vehicles(self.write(shuffled))
        self.assertEqual(actual["vehicle_id"].tolist(), ["1", "2", "3"])

    def test_blank_lines_are_skipped(self):
        actual = read_motc_su_vehicles(
            self.write([SAMPLE[0], "", "   ", SAMPLE[1]])
        )
        self.assertEqual(len(actual), 2)

    def test_empty_file_keeps_schema(self):
        actual = read_motc_su_vehicles(self.write([]))
        self.assertEqual(len(actual), 0)
        self.assertEqual(
            [str(dtype) for dtype in actual.dtypes],
            ["string", "string", "string", "string", "int64", "int64",
             "int64", "float64", "float64", "bool"],
        )

    def test_point_count_must_match_frame_count(self):
        # 宣告 frame 0–1（兩個 frame）卻只給一個 frame 的座標。
        broken = ["1,0,1,BI,AO,c," + points(0, 0, 1, 0, 1, 1, 0, 1)]
        with self.assertRaisesRegex(ValueError, "第 1 行有 8 個軌跡值"):
            read_motc_su_vehicles(self.write(broken))

    def test_invalid_gate_codes_are_rejected(self):
        cases = [
            ("1,0,0,BO,AO,c," + points(*range(8)), "進入路口代號"),
            ("1,0,0,BI,AI,c," + points(*range(8)), "離開路口代號"),
            ("1,0,0,,AO,c," + points(*range(8)), "進入路口代號"),
        ]
        for line, message in cases:
            with self.subTest(line=line):
                with self.assertRaisesRegex(ValueError, message):
                    read_motc_su_vehicles(self.write([line]))

    def test_unknown_vehicle_class_is_rejected(self):
        line = "1,0,0,BI,AO,z," + points(*range(8))
        with self.assertRaisesRegex(ValueError, "車種代號"):
            read_motc_su_vehicles(self.write([line]))

    def test_broken_frames_are_rejected(self):
        cases = [
            ("1,5,2,BI,AO,c," + points(*range(8)), "早於進入 frame"),
            ("1,x,2,BI,AO,c," + points(*range(8)), "不是整數"),
            ("1,-1,2,BI,AO,c," + points(*range(8)), "負數"),
        ]
        for line, message in cases:
            with self.subTest(line=line):
                with self.assertRaisesRegex(ValueError, message):
                    read_motc_su_vehicles(self.write([line]))

    def test_short_line_and_blank_id_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "至少需要 6 個"):
            read_motc_su_vehicles(self.write(["1,0,1,BI"]))
        with self.assertRaisesRegex(ValueError, "車輛 ID 是空白"):
            read_motc_su_vehicles(
                self.write([" ,0,0,BI,AO,c," + points(*range(8))])
            )

    def test_duplicate_vehicle_id_is_rejected(self):
        duplicated = [SAMPLE[0], SAMPLE[0]]
        with self.assertRaisesRegex(ValueError, "車輛 ID 重複"):
            read_motc_su_vehicles(self.write(duplicated))

    def test_invalid_fps_is_rejected(self):
        for value in [0, -1, float("nan"), float("inf"), True, "10"]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "fps"):
                    read_motc_su_vehicles(self.path, fps=value)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_motc_su_vehicles(self.path.with_name("nope.csv"))


class TestReadTracks(MotcSuFileCase):
    def test_hand_calculated_tracks(self):
        actual = read_motc_su_tracks(self.path)
        self.assertEqual(len(actual), 4)          # 2 + 1 + 1 個 frame
        self.assertEqual(actual["vehicle_id"].tolist(), ["1", "1", "2", "3"])
        self.assertEqual(actual["frame"].tolist(), [0, 1, 2, 2])
        for actual_time, expected_time in zip(
            actual["time_s"], [0.0, 1 / 9.99, 2 / 9.99, 2 / 9.99]
        ):
            self.assertAlmostEqual(actual_time, expected_time)

        first = actual.iloc[0]
        self.assertEqual(first["x1_px"], 0.0)
        self.assertEqual(first["y3_px"], 10.0)
        # 中心點是四個角點的平均。
        self.assertAlmostEqual(first["center_x_px"], 5.0)
        self.assertAlmostEqual(first["center_y_px"], 5.0)
        self.assertAlmostEqual(actual.iloc[1]["center_x_px"], 7.0)

    def test_is_complete_is_carried_to_every_frame(self):
        actual = read_motc_su_tracks(self.path)
        self.assertEqual(
            actual.loc[actual["vehicle_id"] == "3", "is_complete"].tolist(),
            [False],
        )

    def test_row_count_matches_total_frame_count(self):
        vehicles = read_motc_su_vehicles(self.path)
        tracks = read_motc_su_tracks(self.path)
        self.assertEqual(len(tracks), int(vehicles["frame_count"].sum()))

    def test_empty_file_keeps_schema(self):
        actual = read_motc_su_tracks(self.write([]))
        self.assertEqual(len(actual), 0)
        self.assertEqual(
            list(actual.columns),
            ["vehicle_id", "frame", "time_s",
             "x1_px", "y1_px", "x2_px", "y2_px",
             "x3_px", "y3_px", "x4_px", "y4_px",
             "center_x_px", "center_y_px", "is_complete"],
        )

    def test_non_numeric_coordinate_is_rejected(self):
        line = "1,0,0,BI,AO,c,0,0,1,0,1,1,0,oops"
        with self.assertRaisesRegex(ValueError, "非數值"):
            read_motc_su_tracks(self.write([line]))


class TestClockwiseMovements(unittest.TestCase):
    def test_four_leg_geometry(self):
        table = clockwise_movements(["A", "B", "C", "D"])
        turns = table.pivot(
            index="entry_gate", columns="exit_gate", values="turn"
        )
        # A 是左側路口，車輛向東行駛：北(B)在左手邊、東(C)是對面、南(D)在右手邊。
        self.assertEqual(turns.loc["A", "A"], "u_turn")
        self.assertEqual(turns.loc["A", "B"], "left")
        self.assertEqual(turns.loc["A", "C"], "straight")
        self.assertEqual(turns.loc["A", "D"], "right")
        # 由 B（北）進入向南行駛時，東(C)換到左手邊。
        self.assertEqual(turns.loc["B", "C"], "left")
        self.assertEqual(turns.loc["B", "A"], "right")
        self.assertEqual(turns.loc["B", "D"], "straight")
        self.assertEqual(len(table), 16)
        self.assertTrue(table["is_allowed"].all())

    def test_two_gates_is_a_segment(self):
        table = clockwise_movements(["IN", "OUT"])
        self.assertEqual(
            table["turn"].tolist(),
            ["u_turn", "straight", "straight", "u_turn"],
        )

    def test_disallowed_pairs_are_marked(self):
        table = clockwise_movements(
            ["A", "B", "C", "D"], disallowed=[("A", "A"), ("B", "C")]
        )
        blocked = table.query("not is_allowed")
        self.assertEqual(
            list(zip(blocked["entry_gate"], blocked["exit_gate"])),
            [("A", "A"), ("B", "C")],
        )

    def test_output_dtypes_and_order(self):
        table = clockwise_movements(["B", "A"])
        self.assertEqual(
            [str(dtype) for dtype in table.dtypes],
            ["string", "string", "string", "bool"],
        )
        # 依 gates 傳入的順序，不重新排序。
        self.assertEqual(table["entry_gate"].tolist(), ["B", "B", "A", "A"])

    def test_invalid_gates_are_rejected(self):
        cases = [
            (["A", "B", "C"], "奇數分支"),
            (["A"], "至少需要兩個"),
            (["A", "A"], "不可重複"),
            (["A", " "], "非空白字串"),
            ("AB", "路口代號的序列"),
        ]
        for gates, message in cases:
            with self.subTest(gates=gates):
                with self.assertRaisesRegex(ValueError, message):
                    clockwise_movements(gates)

    def test_invalid_disallowed_is_rejected(self):
        cases = [
            ([("A", "Z")], "不在 gates 內"),
            ([("A",)], "剛好兩個代號"),
            (["AB"], "每一項必須是"),
            ("A,B", "組合的序列"),
        ]
        for disallowed, message in cases:
            with self.subTest(disallowed=disallowed):
                with self.assertRaisesRegex(ValueError, message):
                    clockwise_movements(["A", "B"], disallowed=disallowed)


class TestEndToEnd(MotcSuFileCase):
    def test_file_to_turn_volume(self):
        vehicles = read_motc_su_vehicles(self.path)
        complete = vehicles.query("is_complete")
        movements = clockwise_movements(
            ["A", "B", "C", "D"], disallowed=[(g, g) for g in "ABCD"]
        )
        result = summarise_turn_volume(
            complete,
            movements=movements,
            vehicle_groups={"小型車": ["c"], "機車": ["m"]},
            pcu_weights=DEFAULT_PCU_WEIGHTS,
        )
        # 車 1：B→A 是右轉的小型車；車 2：A→C 是直行的機車；車 3 被 X 濾掉。
        self.assertEqual(result.summary.counted_vehicle_count, 2)
        right = result.by_turn.query(
            "entry_gate == 'B' and turn == 'right' and vehicle_group == '小型車'"
        )
        self.assertEqual(right["vehicle_count"].item(), 1)
        straight = result.by_turn.query(
            "entry_gate == 'A' and turn == 'straight' and vehicle_group == '機車'"
        )
        self.assertEqual(straight["vehicle_count"].item(), 1)
        self.assertAlmostEqual(result.summary.total_pcu, 1.08 + 0.42)

    def test_incomplete_rows_break_turn_volume_if_not_filtered(self):
        # 契約刻意如此：X 不是路口代號，忘記過濾應該爆炸而不是靜靜少算。
        vehicles = read_motc_su_vehicles(self.path)
        movements = clockwise_movements(["A", "B", "C", "D"])
        with self.assertRaisesRegex(ValueError, "未定義的"):
            summarise_turn_volume(
                vehicles,
                movements=movements,
                vehicle_groups={"小型車": ["c"], "機車": ["m"]},
                pcu_weights=DEFAULT_PCU_WEIGHTS,
            )


class TestVehicleClasses(unittest.TestCase):
    def test_class_table_matches_the_format_definition(self):
        self.assertEqual(
            list(MOTC_SU_VEHICLE_CLASSES),
            ["p", "u", "m", "c", "t", "b", "h", "g"],
        )


if __name__ == "__main__":
    unittest.main()
