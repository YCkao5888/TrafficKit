"""顏色剖析與配色的規格測試。

配色的重點不是「好不好看」，而是**同一台車在整段影片裡是同一個顏色**。
`assign_colors` 的測試大多在守這件事。
"""

import unittest

from traffickit_viz import (
    DEFAULT_PALETTE,
    NAMED_COLORS,
    assign_colors,
    color_to_hex,
    parse_color,
)


class TestParseColor(unittest.TestCase):
    def test_named_colors_are_bgr(self):
        # 紅色的 RGB 是 (255,0,0)，OpenCV 要的 BGR 是 (0,0,255)。
        self.assertEqual(parse_color("red"), (0, 0, 255))
        self.assertEqual(parse_color("blue"), (255, 0, 0))

    def test_names_are_case_insensitive_and_trimmed(self):
        self.assertEqual(parse_color("  RED  "), parse_color("red"))

    def test_hex_is_read_as_rgb_and_returned_as_bgr(self):
        self.assertEqual(parse_color("#FF0000"), (0, 0, 255))
        self.assertEqual(parse_color("#00ff00"), (0, 255, 0))
        self.assertEqual(parse_color("#010203"), (3, 2, 1))

    def test_comma_separated_is_read_as_rgb(self):
        self.assertEqual(parse_color("255,0,0"), (0, 0, 255))
        self.assertEqual(parse_color(" 1 , 2 , 3 "), (3, 2, 1))

    def test_a_bgr_triple_passes_through(self):
        self.assertEqual(parse_color((10, 20, 30)), (10, 20, 30))
        self.assertEqual(parse_color([0, 0, 255]), (0, 0, 255))

    def test_boundary_values_are_accepted(self):
        self.assertEqual(parse_color((0, 0, 0)), (0, 0, 0))
        self.assertEqual(parse_color((255, 255, 255)), (255, 255, 255))

    def test_out_of_range_raises_instead_of_clamping(self):
        # 夾到邊界會讓打錯的值默默變成一個看起來正常的顏色。
        for spec in [(0, 0, 256), (-1, 0, 0), "256,0,0"]:
            with self.subTest(spec=spec):
                with self.assertRaisesRegex(ValueError, "超出 0–255"):
                    parse_color(spec)

    def test_invalid_strings_are_rejected(self):
        cases = [
            ("", "空白"),
            ("#FFF", "#RRGGBB"),
            ("#GGGGGG", "非十六進位"),
            ("1,2", "三個數字"),
            ("1,2,x", "必須是整數"),
            ("chartreuse", "無法解析顏色"),
        ]
        for spec, message in cases:
            with self.subTest(spec=spec):
                with self.assertRaisesRegex(ValueError, message):
                    parse_color(spec)

    def test_wrong_length_sequence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "剛好三個分量"):
            parse_color((1, 2, 3, 4))

    def test_wrong_type_raises_type_error(self):
        with self.assertRaises(TypeError):
            parse_color(255)


class TestColorToHex(unittest.TestCase):
    def test_round_trip(self):
        for name in NAMED_COLORS:
            with self.subTest(name=name):
                bgr = parse_color(name)
                self.assertEqual(parse_color(color_to_hex(bgr)), bgr)

    def test_hex_is_lowercase_and_padded(self):
        self.assertEqual(color_to_hex((3, 2, 1)), "#010203")


class TestAssignColors(unittest.TestCase):
    def test_colors_follow_the_given_order(self):
        colors = assign_colors(["b", "a", "c"])
        self.assertEqual(colors["b"], DEFAULT_PALETTE[0])
        self.assertEqual(colors["a"], DEFAULT_PALETTE[1])
        self.assertEqual(colors["c"], DEFAULT_PALETTE[2])

    def test_palette_wraps_around(self):
        ids = [str(i) for i in range(len(DEFAULT_PALETTE) + 2)]
        colors = assign_colors(ids)
        self.assertEqual(colors[ids[0]], colors[ids[len(DEFAULT_PALETTE)]])

    def test_duplicate_ids_collapse_without_shifting_the_rest(self):
        self.assertEqual(
            assign_colors(["a", "a", "b"]), assign_colors(["a", "b"])
        )

    def test_overrides_keep_their_slot(self):
        # 指定某一台的顏色，不可以讓後面的車跟著換色——那會讓人以為
        # 改了一個設定卻整排都變了。
        plain = assign_colors(["a", "b", "c"])
        overridden = assign_colors(["a", "b", "c"], overrides={"b": "white"})
        self.assertEqual(overridden["b"], (255, 255, 255))
        self.assertEqual(overridden["a"], plain["a"])
        self.assertEqual(overridden["c"], plain["c"])

    def test_override_accepts_every_color_spelling(self):
        colors = assign_colors(
            ["a", "b", "c"],
            overrides={"a": "red", "b": "#00FF00", "c": (255, 0, 0)},
        )
        self.assertEqual(
            [colors["a"], colors["b"], colors["c"]],
            [(0, 0, 255), (0, 255, 0), (255, 0, 0)],
        )

    def test_custom_palette_is_used(self):
        colors = assign_colors(["a", "b"], palette=[(1, 2, 3)])
        self.assertEqual(colors, {"a": (1, 2, 3), "b": (1, 2, 3)})

    def test_empty_input_gives_empty_mapping(self):
        self.assertEqual(assign_colors([]), {})

    def test_empty_palette_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "不可以是空的"):
            assign_colors(["a"], palette=[])

    def test_override_for_an_unknown_vehicle_is_rejected(self):
        # 打錯車號時默默忽略，使用者會以為設定沒生效卻找不到原因。
        with self.assertRaisesRegex(ValueError, "不在 vehicle_ids 內"):
            assign_colors(["a"], overrides={"z": "red"})


if __name__ == "__main__":
    unittest.main()
