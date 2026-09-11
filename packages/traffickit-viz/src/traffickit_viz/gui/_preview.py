"""預覽畫面。

一次只畫一格。舊工具的預覽要按「套用目前設定」才會更新，很容易改了設定
卻看著舊畫面下判斷；這裡改成設定一動就重畫——單格的成本很低，做得到。

解碼與繪製都在主執行緒，所以要靠兩件事撐住流暢度：
 1. ``VideoCapture`` 開著不關，拖曳時只做 seek。
 2. 連續的更新請求用計時器合併，放開滑鼠前不會每一格都畫。
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from .._draw import draw_boxes
from .._style import BoxStyle

#: 連續請求合併的間隔（毫秒）。拖時間軸時不會每一格都解碼。
COALESCE_MS = 60


class FrameSource(QObject):
    """開著不關的影片讀取器。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._capture: cv2.VideoCapture | None = None
        self._path: Path | None = None
        self._next_frame: int | None = None

    def open(self, path: str | os.PathLike[str]) -> None:
        self.close()
        self._path = Path(path)
        self._capture = cv2.VideoCapture(str(self._path))
        if not self._capture.isOpened():
            self.close()
            raise ValueError(f"無法開啟影片：{path}")
        self._next_frame = 0

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self._path = None
        self._next_frame = None

    @property
    def is_open(self) -> bool:
        return self._capture is not None

    def read(self, frame: int) -> np.ndarray | None:
        """讀指定影格，讀不到回 None。"""
        if self._capture is None:
            return None
        # 連續往下讀時不要 seek：seek 會丟掉解碼器的狀態，比循序讀慢得多。
        if self._next_frame != frame:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, image = self._capture.read()
        self._next_frame = frame + 1 if ok else None
        return image if ok else None


class PreviewView(QLabel):
    """把一張 BGR 影像等比例貼滿可用空間。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.setStyleSheet("background: #111; color: #888; border-radius: 6px;")
        self._pixmap: QPixmap | None = None
        self.show_placeholder("選擇影片與軌跡檔後，這裡會顯示預覽")

    def show_placeholder(self, message: str) -> None:
        self._pixmap = None
        self.setText(message)

    def show_image(self, image: np.ndarray) -> None:
        self._pixmap = _to_pixmap(image)
        self._rescale()

    def resizeEvent(self, event) -> None:  # noqa: N802 （Qt 命名）
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        self.setPixmap(
            self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class PreviewController(QObject):
    """把「要看第幾格」變成畫面上的一張圖。"""

    failed = Signal(str)

    def __init__(self, view: PreviewView, parent=None) -> None:
        super().__init__(parent)
        self._view = view
        self._source = FrameSource(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(COALESCE_MS)
        self._timer.timeout.connect(self._render)
        self._pending: tuple[int, pd.DataFrame, BoxStyle] | None = None

    def open(self, path) -> None:
        self._source.open(path)

    def close(self) -> None:
        self._source.close()
        self._view.show_placeholder("選擇影片與軌跡檔後，這裡會顯示預覽")

    def request(self, frame: int, boxes: pd.DataFrame, style: BoxStyle) -> None:
        """要求顯示某一格；短時間內的多次請求只會畫最後一次。"""
        self._pending = (frame, boxes, style)
        self._timer.start()

    def _render(self) -> None:
        if self._pending is None or not self._source.is_open:
            return
        frame, boxes, style = self._pending
        self._pending = None

        image = self._source.read(frame)
        if image is None:
            self._view.show_placeholder(f"讀不到第 {frame} 格")
            return

        try:
            if not boxes.empty:
                draw_boxes(image, boxes, style=style)
        except ValueError as error:
            # 設定與資料不搭（例如顏色表沒涵蓋某台車）時，讓畫面照樣顯示
            # 原始影格，並把原因往上報，不要整個介面卡住。
            self.failed.emit(str(error))

        self._view.show_image(image)


def _to_pixmap(image: np.ndarray) -> QPixmap:
    """BGR ndarray → QPixmap。"""
    height, width = image.shape[:2]
    # Qt 要的是 RGB，而且 QImage 不會複製資料，所以要自己 copy 一份，
    # 否則 numpy 陣列被回收後畫面會變成雜訊。
    rgb = np.ascontiguousarray(image[:, :, ::-1])
    picture = QImage(rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(picture.copy())
