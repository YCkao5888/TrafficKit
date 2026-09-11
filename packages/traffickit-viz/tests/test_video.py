"""影片輸出的規格測試。

這裡會真的寫出影片檔再讀回來驗。影片很小（64x48、20 格），整份測試不到
一秒，但走的是與正式使用完全相同的編解碼路徑——用假的 writer 驗不出
「codec 在這台機器上其實開不起來」這類問題。
"""

import tempfile
import threading
import unittest
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from traffickit_viz import (
    CODECS,
    BoxStyle,
    probe_video,
    render_video,
    resolve_output_path,
)

WIDTH, HEIGHT, FPS, FRAMES = 64, 48, 10.0, 20


def square(left, top=10.0, size=12.0):
    return {
        "x1_px": left, "y1_px": top,
        "x2_px": left, "y2_px": top + size,
        "x3_px": left + size, "y3_px": top + size,
        "x4_px": left + size, "y4_px": top,
    }


def make_video(path: Path, frames: int = FRAMES) -> Path:
    """造一段每格亮度遞增的灰階影片，方便看出讀到的是第幾格。"""
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (WIDTH, HEIGHT)
    )
    assert writer.isOpened(), "測試環境無法建立 MJPG 影片"
    for index in range(frames):
        writer.write(np.full((HEIGHT, WIDTH, 3), index * 5, dtype=np.uint8))
    writer.release()
    return path


def read_back(path: Path):
    capture = cv2.VideoCapture(str(path))
    try:
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ok, first = capture.read()
        return count, fps, width, height, (first if ok else None)
    finally:
        capture.release()


class VideoCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.video = make_video(self.root / "source.avi")
        # 車 1 每格往右移 2 像素，整段都在畫面內。
        self.tracks = pd.DataFrame([
            {"vehicle_id": "1", "frame": index, **square(2.0 + index * 2)}
            for index in range(FRAMES)
        ])
        self.style = BoxStyle({"1": "red"}, label="none", front="none")

    def render(self, **options):
        options.setdefault("output_path", self.root / "out")
        return render_video(self.video, self.tracks, style=self.style, **options)


class TestProbeVideo(VideoCase):
    def test_reports_the_basics(self):
        info = probe_video(self.video)
        self.assertEqual(info.frame_count, FRAMES)
        self.assertAlmostEqual(info.fps, FPS)
        self.assertEqual((info.width, info.height), (WIDTH, HEIGHT))
        self.assertAlmostEqual(info.duration_s, FRAMES / FPS)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            probe_video(self.root / "nope.avi")

    def test_a_file_that_is_not_a_video_raises(self):
        broken = self.root / "broken.avi"
        broken.write_text("not a video", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "無法開啟影片"):
            probe_video(broken)


class TestResolveOutputPath(unittest.TestCase):
    def test_extension_follows_the_codec(self):
        self.assertEqual(
            resolve_output_path("a.mp4", "out.mkv", codec="MJPG").suffix, ".avi"
        )
        self.assertEqual(
            resolve_output_path("a.mp4", "out.avi", codec="mp4v").suffix, ".mp4"
        )

    def test_automatic_name_includes_the_vehicle_ids(self):
        path = resolve_output_path("clip.mp4", vehicle_ids=["2", "4", "5"])
        self.assertIn("_id2-4-5_", path.name)
        self.assertTrue(path.name.startswith("clip_bbox"))

    def test_long_id_lists_are_truncated(self):
        path = resolve_output_path("clip.mp4", vehicle_ids=[str(i) for i in range(20)])
        self.assertIn("-etc", path.name)
        self.assertLess(len(path.name), 80)

    def test_unknown_codec_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "codec"):
            resolve_output_path("a.mp4", codec="nope")


class TestRenderVideo(VideoCase):
    def test_writes_every_frame_of_the_default_range(self):
        result = self.render()
        self.assertEqual(result.start_frame, 0)
        self.assertEqual(result.end_frame, FRAMES - 1)
        self.assertEqual(result.frames_written, FRAMES)
        self.assertTrue(result.is_complete)
        self.assertFalse(result.cancelled)

        count, fps, width, height, _ = read_back(result.output_path)
        self.assertEqual(count, FRAMES)
        self.assertAlmostEqual(fps, FPS)
        self.assertEqual((width, height), (WIDTH, HEIGHT))

    def test_the_boxes_actually_end_up_in_the_output(self):
        plain = self.render(output_path=self.root / "plain")
        # 同一段影片，一次畫框一次不畫，輸出必須不一樣。
        empty = render_video(
            self.video, self.tracks.iloc[:0], style=self.style,
            output_path=self.root / "empty",
        )
        _, _, _, _, with_box = read_back(plain.output_path)
        _, _, _, _, without = read_back(empty.output_path)
        self.assertFalse(np.array_equal(with_box, without))
        # 框是紅的，所以紅色通道應該明顯比原本亮。
        self.assertGreater(int(with_box[:, :, 2].max()), int(without[:, :, 2].max()))

    def test_a_frame_range_limits_the_output(self):
        result = self.render(start_frame=5, end_frame=9)
        self.assertEqual((result.start_frame, result.end_frame), (5, 9))
        self.assertEqual(result.frames_written, 5)
        self.assertEqual(read_back(result.output_path)[0], 5)

    def test_range_defaults_to_the_track_span(self):
        short = self.tracks.query("3 <= frame <= 6")
        result = render_video(
            self.video, short, style=self.style, output_path=self.root / "span"
        )
        self.assertEqual((result.start_frame, result.end_frame), (3, 6))

    def test_an_end_beyond_the_video_is_clamped(self):
        result = self.render(start_frame=0, end_frame=999)
        self.assertEqual(result.end_frame, FRAMES - 1)

    def test_out_scale_changes_the_output_size(self):
        result = self.render(out_scale=0.5)
        _, _, width, height, _ = read_back(result.output_path)
        self.assertEqual((width, height), (WIDTH // 2, HEIGHT // 2))

    def test_every_codec_in_the_table_can_be_written(self):
        # 這張表是對外承諾，裝不起來的 codec 不該留在裡面。
        for codec in CODECS:
            with self.subTest(codec=codec):
                result = self.render(
                    output_path=self.root / f"codec_{codec}", codec=codec
                )
                self.assertTrue(result.output_path.exists())
                self.assertGreater(result.output_path.stat().st_size, 0)

    def test_progress_is_reported_for_every_frame(self):
        seen = []
        self.render(progress=lambda done, total: seen.append((done, total)))
        self.assertEqual(len(seen), FRAMES)
        self.assertEqual(seen[0], (1, FRAMES))
        self.assertEqual(seen[-1], (FRAMES, FRAMES))

    def test_cancelling_stops_early_and_keeps_what_was_written(self):
        cancel = threading.Event()
        cancel.set()
        result = self.render(cancel=cancel)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.frames_written, 0)
        self.assertFalse(result.is_complete)
        # 半截的檔案留著比較好除錯，不自動刪除。
        self.assertTrue(result.output_path.exists())

    def test_frame_offset_shifts_the_tracks_onto_the_video(self):
        result = self.render(frame_offset=5)
        self.assertEqual((result.start_frame, result.end_frame), (5, FRAMES - 1))

    def test_vehicles_with_no_track_in_range_are_reported(self):
        result = self.render(start_frame=0, end_frame=2)
        self.assertEqual(result.drawn_vehicle_ids, ("1",))
        self.assertEqual(result.missing_vehicle_ids, ())

        late = self.tracks.assign(
            vehicle_id=lambda frame: np.where(frame["frame"] > 10, "2", "1")
        )
        style = BoxStyle({"1": "red", "2": "blue"}, label="none", front="none")
        result = render_video(
            self.video, late, style=style,
            output_path=self.root / "late", start_frame=0, end_frame=2,
        )
        self.assertEqual(result.drawn_vehicle_ids, ("1",))
        self.assertEqual(result.missing_vehicle_ids, ("2",))

    def test_show_frame_number_paints_the_overlay(self):
        without = self.render(output_path=self.root / "no_overlay")
        with_overlay = self.render(
            output_path=self.root / "overlay", show_frame_number=True
        )
        _, _, _, _, plain = read_back(without.output_path)
        _, _, _, _, stamped = read_back(with_overlay.output_path)
        self.assertFalse(np.array_equal(plain, stamped))

    def test_empty_tracks_still_produce_the_whole_video(self):
        result = render_video(
            self.video, self.tracks.iloc[:0], style=self.style,
            output_path=self.root / "none",
        )
        self.assertEqual(result.frames_written, FRAMES)
        self.assertEqual(result.drawn_vehicle_ids, ())


class TestRenderValidation(VideoCase):
    def test_missing_video_raises(self):
        with self.assertRaises(FileNotFoundError):
            render_video(self.root / "nope.avi", self.tracks, style=self.style)

    def test_invalid_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "早於 start_frame"):
            self.render(start_frame=9, end_frame=3)
        with self.assertRaisesRegex(ValueError, "負數"):
            self.render(start_frame=-1, end_frame=3)
        with self.assertRaisesRegex(ValueError, "超出影片範圍"):
            self.render(start_frame=999, end_frame=1000)

    def test_invalid_options_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "codec"):
            self.render(codec="nope")
        for scale in (0, -1):
            with self.subTest(scale=scale):
                with self.assertRaisesRegex(ValueError, "out_scale"):
                    self.render(out_scale=scale)

    def test_missing_track_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "缺少必要欄位"):
            render_video(
                self.video, self.tracks.drop(columns=["frame"]), style=self.style
            )

    def test_a_vehicle_without_a_color_is_rejected(self):
        style = BoxStyle({"other": "red"}, label="none", front="none")
        with self.assertRaisesRegex(ValueError, "顏色表裡沒有車輛"):
            render_video(
                self.video, self.tracks, style=style,
                output_path=self.root / "bad",
            )

    def test_wrong_type_raises_type_error(self):
        with self.assertRaises(TypeError):
            render_video(self.video, [1, 2, 3], style=self.style)


if __name__ == "__main__":
    unittest.main()
