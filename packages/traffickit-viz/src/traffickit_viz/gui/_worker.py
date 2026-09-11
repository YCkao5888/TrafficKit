"""在背景執行緒輸出影片。

輸出一段 4K 影片要幾分鐘，放在主執行緒會讓整個視窗沒有反應。這裡把它
搬到 QThread，進度與結果用 signal 送回主執行緒——Qt 的 widget 只能在主
執行緒動，所以 worker 絕對不碰任何 widget。
"""

from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject, Signal

from .._style import BoxStyle
from .._video import RenderResult, render_video


class RenderWorker(QObject):
    """一次輸出。建立後 ``moveToThread``，再呼叫 :meth:`run`。"""

    progress = Signal(int, int)          # 已寫入, 總數
    finished = Signal(object)            # RenderResult
    failed = Signal(str)

    def __init__(
        self,
        *,
        video_path: Path,
        tracks: pd.DataFrame,
        style: BoxStyle,
        output_path: Path,
        start_frame: int,
        end_frame: int,
        codec: str,
        out_scale: float,
        show_frame_number: bool,
    ) -> None:
        super().__init__()
        self._options = dict(
            video_path=video_path,
            tracks=tracks,
            style=style,
            output_path=output_path,
            start_frame=start_frame,
            end_frame=end_frame,
            codec=codec,
            out_scale=out_scale,
            show_frame_number=show_frame_number,
        )
        self.cancel = threading.Event()

    def run(self) -> None:
        options = dict(self._options)
        video_path = options.pop("video_path")
        tracks = options.pop("tracks")
        try:
            result: RenderResult = render_video(
                video_path, tracks, cancel=self.cancel,
                progress=lambda done, total: self.progress.emit(done, total),
                **options,
            )
        except Exception as error:                  # noqa: BLE001
            # 背景執行緒的例外若不接住就只會印在主控台，介面完全沒反應。
            self.failed.emit(f"{type(error).__name__}：{error}")
            return
        self.finished.emit(result)
