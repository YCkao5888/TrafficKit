"""繪製與樣式的規格測試。

畫面不好用等式驗，所以測的是**看得出差別的性質**：該被塗到的像素有沒有變、
不該被碰的有沒有保持原樣、以及缺資料時會不會拋錯而不是畫出錯的東西。
"""

import unittest

import numpy as np
import pandas as pd

from traffickit_viz import BoxStyle, assign_colors, default_style, draw_boxes

RED = (0, 0, 255)

# 一台車，框在 (20,20)-(50,40)，車頭那條邊在左側（x1/x2）。
BOX = pd.DataFrame([{
    "vehicle_id": "1", "vehicle_class": "c",
    "x1_px": 20.0, "y1_px": 20.0,
    "x2_px": 20.0, "y2_px": 40.0,
    "x3_px": 50.0, "y3_px": 40.0,
    "x4_px": 50.0, "y4_px": 20.0,
    "heading_x": -1.0, "heading_y": 0.0,
}])


def blank(height=60, width=80):
    return np.zeros((height, width, 3), dtype=np.uint8)


def painted(image):
    """被畫到的像素數量。"""
    return int(np.count_nonzero(image.any(axis=2)))


def shifted(boxes, dx):
    """把框整個往右移 dx 像素。"""
    moved = boxes.copy()
    for name in ("x1_px", "x2_px", "x3_px", "x4_px"):
        moved[name] += dx
    return moved


class TestDrawBoxes(unittest.TestCase):
    def test_fill_covers_the_interior_exactly(self):
        image = blank()
        style = BoxStyle({"1": RED}, label="none", front="none", fill_alpha=1.0)
        draw_boxes(image, BOX, style=style)
        self.assertEqual(tuple(image[30, 30]), RED)      # 框內
        self.assertEqual(tuple(image[5, 5]), (0, 0, 0))  # 框外

    def test_outline_is_drawn_without_filling(self):
        image = blank()
        style = BoxStyle({"1": RED}, label="none", front="none")
        draw_boxes(image, BOX, style=style)
        self.assertTrue(image[20, 30].any(), "上緣應該有框線")
        self.assertFalse(image[30, 30].any(), "fill_alpha=0 時框內不該被塗")

    def test_partial_fill_blends_instead_of_replacing(self):
        image = blank()
        style = BoxStyle({"1": RED}, label="none", front="none", fill_alpha=0.5)
        draw_boxes(image, BOX, style=style)
        red = int(image[30, 30][2])
        self.assertGreater(red, 0)
        self.assertLess(red, 255)

    def test_thicker_lines_paint_more_pixels(self):
        thin, thick = blank(), blank()
        common = dict(label="none", front="none")
        draw_boxes(thin, BOX, style=BoxStyle({"1": RED}, thickness=1, **common))
        draw_boxes(thick, BOX, style=BoxStyle({"1": RED}, thickness=5, **common))
        self.assertGreater(painted(thick), painted(thin))

    def test_the_image_is_modified_in_place_and_returned(self):
        image = blank()
        returned = draw_boxes(image, BOX, style=default_style(["1"]))
        self.assertIs(returned, image)

    def test_boxes_are_not_modified(self):
        before = BOX.copy()
        draw_boxes(blank(), BOX, style=default_style(["1"]))
        pd.testing.assert_frame_equal(BOX, before)

    def test_empty_boxes_leave_the_image_untouched(self):
        image = blank()
        draw_boxes(image, BOX.iloc[:0], style=default_style(["1"]))
        self.assertEqual(painted(image), 0)

    def test_a_partly_visible_box_still_draws_the_visible_part(self):
        # 車輛進出畫面邊緣時本來就會有一部分在外面，露出的部分要照畫。
        partial = shifted(BOX, 40)          # 框變成 x=60..90，畫面寬 80
        image = blank()
        draw_boxes(image, partial, style=default_style(["1"]))
        self.assertGreater(painted(image), 0)

    def test_a_fully_invisible_box_paints_nothing(self):
        # 標籤的位置會夾進畫面內，不整台跳過的話，畫面邊緣會浮著一個
        # 沒有框的標籤——舊工具就是這樣。
        image = blank()
        draw_boxes(image, shifted(BOX, 500), style=default_style(["1"]))
        self.assertEqual(painted(image), 0)

    def test_each_vehicle_uses_its_own_color(self):
        two = pd.concat([BOX, BOX.assign(vehicle_id="2")], ignore_index=True)
        two.loc[1, ["x1_px", "x2_px", "x3_px", "x4_px"]] = [0.0, 0.0, 10.0, 10.0]
        image = blank()
        style = BoxStyle(
            {"1": (0, 0, 255), "2": (255, 0, 0)},
            label="none", front="none", fill_alpha=1.0,
        )
        draw_boxes(image, two, style=style)
        self.assertEqual(tuple(image[30, 30]), (0, 0, 255))
        self.assertEqual(tuple(image[30, 5]), (255, 0, 0))


class TestLabels(unittest.TestCase):
    def test_label_paints_above_the_box(self):
        without = blank()
        with_label = blank()
        draw_boxes(without, BOX,
                   style=BoxStyle({"1": RED}, label="none", front="none"))
        draw_boxes(with_label, BOX,
                   style=BoxStyle({"1": RED}, label="id", front="none"))
        self.assertGreater(painted(with_label), painted(without))

    def test_class_label_requires_the_class_column(self):
        style = BoxStyle({"1": RED}, label="class", front="none")
        with self.assertRaisesRegex(ValueError, "vehicle_class"):
            draw_boxes(blank(), BOX.drop(columns=["vehicle_class"]), style=style)

    def test_id_label_does_not_require_the_class_column(self):
        style = BoxStyle({"1": RED}, label="id", front="none")
        draw_boxes(blank(), BOX.drop(columns=["vehicle_class"]), style=style)


class TestFrontMarker(unittest.TestCase):
    def test_edge_marker_recolours_the_front_edge(self):
        image = blank()
        style = BoxStyle(
            {"1": RED}, label="none", front="edge", front_color="white"
        )
        draw_boxes(image, BOX, style=style)
        # 車頭邊是 x1→x2，也就是 x=20 那一條；車尾邊 x=50 應維持車身顏色。
        self.assertEqual(tuple(image[30, 20]), (255, 255, 255))
        self.assertEqual(tuple(image[30, 50]), RED)

    def test_arrow_requires_heading_columns(self):
        style = BoxStyle({"1": RED}, front="arrow", label="none")
        with self.assertRaisesRegex(ValueError, "heading_x"):
            draw_boxes(blank(), BOX.drop(columns=["heading_x", "heading_y"]),
                       style=style)

    def test_arrow_is_drawn_when_heading_is_known(self):
        without = blank()
        with_arrow = blank()
        draw_boxes(without, BOX,
                   style=BoxStyle({"1": RED}, front="none", label="none"))
        draw_boxes(with_arrow, BOX,
                   style=BoxStyle({"1": RED}, front="arrow", label="none"))
        self.assertGreater(painted(with_arrow), painted(without))

    def test_unknown_heading_skips_the_arrow_without_failing(self):
        # 算不出方向就不畫，總比畫一個指向任意方向的箭頭好。
        unknown = BOX.assign(heading_x=np.nan, heading_y=np.nan)
        image = blank()
        draw_boxes(image, unknown,
                   style=BoxStyle({"1": RED}, front="arrow", label="none"))
        with_arrow = blank()
        draw_boxes(with_arrow, BOX,
                   style=BoxStyle({"1": RED}, front="arrow", label="none"))
        self.assertLess(painted(image), painted(with_arrow))


class TestInputChecks(unittest.TestCase):
    def test_unknown_vehicle_in_the_color_table_is_rejected(self):
        # 臨時補一個顏色會讓同一台車在不同影格變色，所以寧可拋錯。
        style = BoxStyle({"2": RED}, label="none", front="none")
        with self.assertRaisesRegex(ValueError, "顏色表裡沒有車輛"):
            draw_boxes(blank(), BOX, style=style)

    def test_non_finite_coordinates_are_rejected(self):
        broken = BOX.assign(x1_px=np.nan)
        with self.assertRaisesRegex(ValueError, "非有限值"):
            draw_boxes(blank(), broken, style=default_style(["1"]))

    def test_missing_corner_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "缺少必要欄位"):
            draw_boxes(blank(), BOX.drop(columns=["x3_px"]),
                       style=default_style(["1"]))

    def test_image_shape_and_dtype_are_checked(self):
        style = default_style(["1"])
        cases = [
            (np.zeros((60, 80), dtype=np.uint8), "BGR 影像"),
            (np.zeros((60, 80, 4), dtype=np.uint8), "BGR 影像"),
            (np.zeros((60, 80, 3), dtype=np.float32), "uint8"),
        ]
        for image, message in cases:
            with self.subTest(shape=image.shape, dtype=image.dtype):
                with self.assertRaisesRegex(ValueError, message):
                    draw_boxes(image, BOX, style=style)

    def test_wrong_types_raise_type_error(self):
        style = default_style(["1"])
        with self.assertRaises(TypeError):
            draw_boxes("not an image", BOX, style=style)
        with self.assertRaises(TypeError):
            draw_boxes(blank(), [1, 2, 3], style=style)


class TestBoxStyle(unittest.TestCase):
    def test_color_spellings_are_normalised_to_bgr(self):
        style = BoxStyle({"1": "red"}, front_color="#FFFFFF")
        self.assertEqual(style.colors["1"], (0, 0, 255))
        self.assertEqual(style.front_color, (255, 255, 255))

    def test_bad_colors_fail_when_the_style_is_built(self):
        # 等到畫第 3000 格才炸就太晚了。
        with self.assertRaises(ValueError):
            BoxStyle({"1": "chartreuse"})

    def test_invalid_options_are_rejected(self):
        cases = [
            (dict(thickness=0), "至少是 1"),
            (dict(thickness=1.5), "必須是整數"),
            (dict(label="huge"), "不是可用選項"),
            (dict(front="sideways"), "不是可用選項"),
            (dict(font_scale=0), "必須大於 0"),
            (dict(fill_alpha=1.5), "介於 0 與 1"),
            (dict(fill_alpha=-0.1), "介於 0 與 1"),
        ]
        for options, message in cases:
            with self.subTest(**options):
                with self.assertRaisesRegex(ValueError, message):
                    BoxStyle({"1": RED}, **options)

    def test_boundary_values_are_accepted(self):
        BoxStyle({"1": RED}, thickness=1, fill_alpha=0.0)
        BoxStyle({"1": RED}, fill_alpha=1.0)

    def test_requirements_are_reported(self):
        self.assertFalse(BoxStyle({}, label="id", front="edge").needs_heading)
        self.assertTrue(BoxStyle({}, front="arrow").needs_heading)
        self.assertTrue(BoxStyle({}, front="both").needs_heading)
        self.assertFalse(BoxStyle({}, label="id").needs_vehicle_class)
        self.assertTrue(BoxStyle({}, label="both").needs_vehicle_class)

    def test_default_style_assigns_colors_in_order(self):
        style = default_style(["a", "b"], label="none")
        self.assertEqual(style.colors["a"], assign_colors(["a", "b"])["a"])
        self.assertEqual(style.label, "none")


if __name__ == "__main__":
    unittest.main()
