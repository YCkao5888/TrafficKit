"""轉向流量統計的規格測試。

測試驗證契約中的交通定義與資料品質政策，不重寫一遍算法當作預期答案。
資料與手算答案見 docs/worksheets/volume.turn_volume.md。
"""

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from traffickit.volume import (
    DEFAULT_PCU_WEIGHTS,
    DEFAULT_VEHICLE_GROUPS,
    TURNS,
    TurnVolume,
    summarise_turn_volume,
)

MOVEMENT_DTYPES = {
    "entry_gate": "string",
    "exit_gate": "string",
    "turn": "string",
    "vehicle_group": "string",
    "is_allowed": "bool",
    "vehicle_count": "int64",
    "pcu_weight": "float64",
    "pcu": "float64",
}

BY_TURN_DTYPES = {
    key: value for key, value in MOVEMENT_DTYPES.items() if key != "exit_gate"
}

GROUPS = {"小型車": ["c"], "機車": ["m"]}
WEIGHTS = {name: DEFAULT_PCU_WEIGHTS[name] for name in GROUPS}


def frame(rows, dtypes) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=list(dtypes)).astype(dtypes)


class TestSummariseTurnVolume(unittest.TestCase):
    def setUp(self):
        # N 有兩個右轉出口（W 與 NE），用來檢查 by_turn 的加總。
        # E→E 迴轉不允許，資料裡卻有一台，用來檢查違規轉向照實計數。
        self.movements = pd.DataFrame([
            ("N", "E", "left", True),
            ("N", "S", "straight", True),
            ("N", "W", "right", True),
            ("N", "NE", "right", True),
            ("E", "N", "right", True),
            ("E", "W", "straight", True),
            ("E", "E", "u_turn", False),
        ], columns=["entry_gate", "exit_gate", "turn", "is_allowed"])

        self.vehicles = pd.DataFrame([
            ("V1", "N", "S", "c"),
            ("V2", "N", "S", "c"),
            ("V3", "N", "S", "m"),
            ("V4", "N", "E", "c"),
            ("V5", "E", "W", "m"),
            ("V6", "E", "E", "m"),
            ("V7", "N", "S", "p"),   # 行人，未列入分組
            ("V8", "N", "NE", "c"),
        ], columns=["vehicle_id", "entry_gate", "exit_gate", "vehicle_class"])

    def run_default(self, **overrides):
        kwargs = {
            "movements": self.movements,
            "vehicle_groups": GROUPS,
            "pcu_weights": WEIGHTS,
        }
        kwargs.update(overrides)
        vehicles = kwargs.pop("vehicles", self.vehicles)
        return summarise_turn_volume(vehicles, **kwargs)

    def test_hand_calculated_movements(self):
        actual = self.run_default().movements
        expected = frame([
            ("E", "W", "straight", "小型車", True, 0, 1.00, 0.00),
            ("E", "W", "straight", "機車", True, 1, 0.42, 0.42),
            ("E", "N", "right", "小型車", True, 0, 1.08, 0.00),
            ("E", "N", "right", "機車", True, 0, 0.45, 0.00),
            ("E", "E", "u_turn", "小型車", False, 0, 1.05, 0.00),
            ("E", "E", "u_turn", "機車", False, 1, 0.43, 0.43),
            ("N", "E", "left", "小型車", True, 1, 1.05, 1.05),
            ("N", "E", "left", "機車", True, 0, 0.43, 0.00),
            ("N", "S", "straight", "小型車", True, 2, 1.00, 2.00),
            ("N", "S", "straight", "機車", True, 1, 0.42, 0.42),
            ("N", "NE", "right", "小型車", True, 1, 1.08, 1.08),
            ("N", "NE", "right", "機車", True, 0, 0.45, 0.00),
            ("N", "W", "right", "小型車", True, 0, 1.08, 0.00),
            ("N", "W", "right", "機車", True, 0, 0.45, 0.00),
        ], MOVEMENT_DTYPES)
        assert_frame_equal(actual, expected)

    def test_by_turn_merges_two_exits_sharing_one_turn(self):
        actual = self.run_default().by_turn
        expected = frame([
            ("E", "straight", "小型車", True, 0, 1.00, 0.00),
            ("E", "straight", "機車", True, 1, 0.42, 0.42),
            ("E", "right", "小型車", True, 0, 1.08, 0.00),
            ("E", "right", "機車", True, 0, 0.45, 0.00),
            ("E", "u_turn", "小型車", False, 0, 1.05, 0.00),
            ("E", "u_turn", "機車", False, 1, 0.43, 0.43),
            ("N", "left", "小型車", True, 1, 1.05, 1.05),
            ("N", "left", "機車", True, 0, 0.43, 0.00),
            ("N", "straight", "小型車", True, 2, 1.00, 2.00),
            ("N", "straight", "機車", True, 1, 0.42, 0.42),
            # N→W 的 0 台與 N→NE 的 1 台合併成一列。
            ("N", "right", "小型車", True, 1, 1.08, 1.08),
            ("N", "right", "機車", True, 0, 0.45, 0.00),
        ], BY_TURN_DTYPES)
        assert_frame_equal(actual, expected)

    def test_summary_matches_hand_calculation(self):
        summary = self.run_default().summary
        self.assertEqual(summary.input_vehicle_count, 8)
        self.assertEqual(summary.counted_vehicle_count, 7)
        self.assertEqual(summary.unassigned_vehicle_count, 1)
        self.assertEqual(summary.unassigned_classes, ("p",))
        self.assertEqual(summary.disallowed_vehicle_count, 1)
        # 2*1.0 + 1*0.42 + 1*1.05 + 1*1.08 + 1*0.42 + 1*0.43
        self.assertAlmostEqual(summary.total_pcu, 5.40)
        self.assertEqual(
            summary.input_vehicle_count,
            summary.counted_vehicle_count + summary.unassigned_vehicle_count,
        )

    def test_allowed_movement_with_no_vehicle_is_kept(self):
        result = self.run_default()
        empty = result.movements.query(
            "entry_gate == 'E' and exit_gate == 'N'"
        )
        self.assertEqual(len(empty), 2)
        self.assertTrue(empty["is_allowed"].all())
        self.assertEqual(empty["vehicle_count"].tolist(), [0, 0])

    def test_disallowed_movement_with_vehicle_is_counted_and_flagged(self):
        row = self.run_default().movements.query(
            "entry_gate == 'E' and exit_gate == 'E' and vehicle_group == '機車'"
        )
        self.assertEqual(row["vehicle_count"].item(), 1)
        self.assertFalse(bool(row["is_allowed"].item()))

    def test_by_turn_is_allowed_is_true_when_any_exit_allows(self):
        movements = self.movements.copy()
        # 只關掉 N→W，N→NE 仍允許：by_turn 的 (N, right) 應維持 True。
        movements.loc[
            (movements["entry_gate"] == "N") & (movements["exit_gate"] == "W"),
            "is_allowed",
        ] = False
        result = self.run_default(movements=movements)
        row = result.by_turn.query("entry_gate == 'N' and turn == 'right'")
        self.assertTrue(row["is_allowed"].all())

    def test_group_and_turn_order_follow_declaration(self):
        result = self.run_default(
            vehicle_groups={"機車": ["m"], "小型車": ["c"]},
            pcu_weights=WEIGHTS,
        )
        self.assertEqual(result.vehicle_groups, ("機車", "小型車"))
        self.assertEqual(
            result.by_turn.query("entry_gate == 'N' and turn == 'left'")[
                "vehicle_group"
            ].tolist(),
            ["機車", "小型車"],
        )
        # 轉向永遠依 TURNS 的順序，與 movements 的列順序無關。
        self.assertEqual(result.turns, TURNS)
        self.assertEqual(
            result.by_turn.query("entry_gate == 'N'")["turn"].unique().tolist(),
            ["left", "straight", "right"],
        )

    def test_unassigned_classes_are_excluded_and_reported(self):
        vehicles = self.vehicles.copy()
        vehicles.loc[len(vehicles)] = ("V9", "N", "S", "x")
        summary = self.run_default(vehicles=vehicles).summary
        self.assertEqual(summary.unassigned_vehicle_count, 2)
        self.assertEqual(summary.unassigned_classes, ("p", "x"))
        self.assertEqual(summary.counted_vehicle_count, 7)

    def test_unsorted_rows_duplicate_index_and_no_mutation(self):
        shuffled = self.vehicles.sample(frac=1, random_state=3).copy()
        shuffled.index = [0] * len(shuffled)
        before = shuffled.copy(deep=True)
        moves_before = self.movements.copy(deep=True)

        actual = self.run_default(vehicles=shuffled)
        expected = self.run_default()
        assert_frame_equal(actual.movements, expected.movements)
        assert_frame_equal(actual.by_turn, expected.by_turn)
        assert_frame_equal(shuffled, before)
        assert_frame_equal(self.movements, moves_before)

    def test_extra_columns_are_ignored(self):
        with_extra = self.vehicles.assign(timestamp_s=range(len(self.vehicles)))
        assert_frame_equal(
            self.run_default(vehicles=with_extra).movements,
            self.run_default().movements,
        )

    def test_empty_vehicles_keep_the_full_grid(self):
        result = self.run_default(vehicles=self.vehicles.iloc[:0])
        self.assertEqual(len(result.movements), 14)
        self.assertEqual(result.movements["vehicle_count"].sum(), 0)
        self.assertAlmostEqual(result.summary.total_pcu, 0.0)
        self.assertEqual(result.summary.input_vehicle_count, 0)
        self.assertEqual(result.summary.unassigned_classes, ())
        self.assertEqual(
            [str(dtype) for dtype in result.movements.dtypes],
            list(MOVEMENT_DTYPES.values()),
        )

    def test_result_object_is_frozen(self):
        result = self.run_default()
        self.assertIsInstance(result, TurnVolume)
        with self.assertRaises(Exception):
            result.turns = ()

    def test_undefined_movement_in_data_is_rejected(self):
        vehicles = self.vehicles.copy()
        vehicles.loc[len(vehicles)] = ("V9", "S", "N", "c")
        with self.assertRaisesRegex(ValueError, "未定義的"):
            self.run_default(vehicles=vehicles)

    def test_duplicate_vehicle_id_is_rejected(self):
        vehicles = pd.concat([self.vehicles, self.vehicles.iloc[[0]]])
        with self.assertRaisesRegex(ValueError, "vehicle_id 不可重複"):
            self.run_default(vehicles=vehicles)

    def test_non_dataframe_is_rejected(self):
        with self.assertRaisesRegex(TypeError, "vehicles"):
            self.run_default(vehicles=[{"vehicle_id": "V1"}])
        with self.assertRaisesRegex(TypeError, "movements"):
            self.run_default(movements=ZONE_CONFIG_MOVEMENTS)

    def test_missing_columns_are_reported(self):
        with self.assertRaisesRegex(ValueError, "vehicles 缺少必要欄位"):
            self.run_default(vehicles=self.vehicles.drop(columns="exit_gate"))
        with self.assertRaisesRegex(ValueError, "movements 缺少必要欄位"):
            self.run_default(movements=self.movements.drop(columns="turn"))

    def test_blank_labels_are_rejected(self):
        for column in ("vehicle_id", "entry_gate", "exit_gate", "vehicle_class"):
            with self.subTest(column=column):
                invalid = self.vehicles.copy()
                invalid.loc[0, column] = "  "
                with self.assertRaisesRegex(ValueError, column):
                    self.run_default(vehicles=invalid)

    def test_invalid_movements_are_rejected(self):
        unknown_turn = self.movements.copy()
        unknown_turn.loc[0, "turn"] = "u-turn"
        with self.assertRaisesRegex(ValueError, "turn 只接受"):
            self.run_default(movements=unknown_turn)

        not_bool = self.movements.astype({"is_allowed": "int64"})
        with self.assertRaisesRegex(ValueError, "is_allowed"):
            self.run_default(movements=not_bool)

        duplicated = pd.concat([self.movements, self.movements.iloc[[0]]])
        with self.assertRaisesRegex(ValueError, r"\(entry_gate, exit_gate\)"):
            self.run_default(movements=duplicated)

        with self.assertRaisesRegex(ValueError, "movements 至少需要一列"):
            self.run_default(movements=self.movements.iloc[:0])

    def test_invalid_vehicle_groups_are_rejected(self):
        cases = [
            ({}, "至少需要一個分組"),
            ({"  ": ["c"]}, "分組名稱"),
            ({"小型車": []}, "至少需要一個車種"),
            ({"小型車": "c"}, "車種代碼的序列"),
            ({"小型車": [" "]}, "車種代碼"),
            ({"A": ["c"], "B": ["c"]}, "只能屬於一個分組"),
            ([("小型車", ["c"])], "分組名稱 → 車種代碼"),
        ]
        for groups, message in cases:
            with self.subTest(groups=groups):
                with self.assertRaisesRegex(ValueError, message):
                    self.run_default(
                        vehicle_groups=groups, pcu_weights=DEFAULT_PCU_WEIGHTS
                    )

    def test_invalid_pcu_weights_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "缺少分組"):
            self.run_default(pcu_weights={"小型車": WEIGHTS["小型車"]})

        missing_turn = {
            "小型車": {"left": 1.05, "straight": 1.0, "right": 1.08},
            "機車": WEIGHTS["機車"],
        }
        with self.assertRaisesRegex(ValueError, "缺少轉向"):
            self.run_default(pcu_weights=missing_turn)

        for bad in [-1.0, float("nan"), float("inf"), True, "1.0"]:
            with self.subTest(value=bad):
                weights = {
                    "小型車": dict(WEIGHTS["小型車"], left=bad),
                    "機車": WEIGHTS["機車"],
                }
                with self.assertRaisesRegex(ValueError, "pcu_weights"):
                    self.run_default(pcu_weights=weights)

        with self.assertRaisesRegex(ValueError, "pcu_weights 必須是"):
            self.run_default(pcu_weights=[("小型車", {})])

    def test_weights_only_needed_for_turns_actually_defined(self):
        # movements 只用到 straight，缺其他轉向的權重也應該可以算。
        movements = self.movements.query("turn == 'straight'").copy()
        vehicles = self.vehicles.query("exit_gate in ('S', 'W')").copy()
        result = summarise_turn_volume(
            vehicles,
            movements=movements,
            vehicle_groups=GROUPS,
            pcu_weights={
                "小型車": {"straight": 1.0},
                "機車": {"straight": 0.42},
            },
        )
        self.assertEqual(result.turns, ("straight",))
        self.assertAlmostEqual(result.summary.total_pcu, 2 * 1.0 + 2 * 0.42)


class TestDefaults(unittest.TestCase):
    def test_default_groups_and_weights_line_up(self):
        self.assertEqual(
            set(DEFAULT_VEHICLE_GROUPS), set(DEFAULT_PCU_WEIGHTS)
        )
        for group, weights in DEFAULT_PCU_WEIGHTS.items():
            with self.subTest(group=group):
                self.assertEqual(tuple(weights), TURNS)
                self.assertTrue(all(value > 0 for value in weights.values()))
        classes = [
            code
            for codes in DEFAULT_VEHICLE_GROUPS.values()
            for code in codes
        ]
        self.assertEqual(len(classes), len(set(classes)))

    def test_defaults_are_usable_as_passed_in_arguments(self):
        movements = pd.DataFrame(
            [("N", "S", "straight", True)],
            columns=["entry_gate", "exit_gate", "turn", "is_allowed"],
        )
        vehicles = pd.DataFrame(
            [("V1", "N", "S", "b")],
            columns=["vehicle_id", "entry_gate", "exit_gate", "vehicle_class"],
        )
        result = summarise_turn_volume(
            vehicles,
            movements=movements,
            vehicle_groups=DEFAULT_VEHICLE_GROUPS,
            pcu_weights=DEFAULT_PCU_WEIGHTS,
        )
        self.assertAlmostEqual(result.summary.total_pcu, 1.8)
        self.assertEqual(result.summary.counted_vehicle_count, 1)


ZONE_CONFIG_MOVEMENTS = [
    {"from": "N", "to": "S", "category": "straight", "is_allowed": True},
]


if __name__ == "__main__":
    unittest.main()
