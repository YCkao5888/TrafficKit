"""讀影片、疊上車身框、寫成新影片。

這是整個套件唯一會碰檔案的地方。
"""

from __future__ import annotations

import datetime
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import cv2
import numpy as np
import pandas as pd

from ._draw import draw_boxes
from ._style import BoxStyle

#: 可用的輸出編碼：``名稱 → (fourcc, 副檔名)``。
#:
#: ``MJPG`` 最快、檔案最大，而且是 OpenCV 自帶的 AVI 寫入器，不靠外部元件，
#: 因此當預設值最不會在別人的機器上出事。``XVID`` 壓縮率好但吃 CPU，
#: ``mp4v`` 相容性佳。
CODECS: dict[str, tuple[str, str]] = {
    "MJPG": ("MJPG", ".avi"),
    "XVID": ("XVID", ".avi"),
    "mp4v": ("mp4v", ".mp4"),
}

_OVERLAY_ORIGIN = (10, 28)


@dataclass(frozen=True)
class VideoInfo:
    """影片的基本資訊。"""

    path: Path
    frame_count: int
    fps: float
    width: int
    height: int

    @property
    def duration_s(self) -> float:
        return self.frame_count / self.fps


@dataclass(frozen=True)
class RenderResult:
    """一次輸出實際做了什麼。

    這裡回報的是**事實**，不是警告文字：呼叫端要印成訊息、顯示在介面上，
    還是當成錯誤處理，由呼叫端決定。本套件不 print。
    """

    output_path: Path
    start_frame: int
    end_frame: int
    frames_written: int
    drawn_vehicle_ids: tuple[str, ...]
    missing_vehicle_ids: tuple[str, ...]
    cancelled: bool

    @property
    def is_complete(self) -> bool:
        """要輸出的影格是不是都寫出去了。"""
        return (
            not self.cancelled
            and self.frames_written == self.end_frame - self.start_frame + 1
        )


def probe_video(path: str | os.PathLike[str]) -> VideoInfo:
    """讀影片的幀率、影格數與尺寸，不解碼任何畫面。

    Raises
    ------
    FileNotFoundError
        檔案不存在。
    ValueError
        檔案打不開，或取不到有效的幀率。
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到影片：{path}")

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(f"無法開啟影片（格式不支援或檔案損壞）：{path}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not fps or not np.isfinite(fps) or fps <= 0:
            raise ValueError(f"無法取得影片幀率：{path}")
        return VideoInfo(
            path=path,
            frame_count=int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
            fps=float(fps),
            width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
    finally:
        capture.release()


def resolve_output_path(
    input_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str] | None = None,
    *,
    codec: str = "MJPG",
    vehicle_ids: Sequence[str] | None = None,
) -> Path:
    """決定輸出檔路徑，**副檔名一律依 codec 修正**。

    沒指定 output_path 時，以輸入檔名加上車號與時間戳記自動命名，例如
    ``原檔名_bbox_id2-4-5_20260911153000.avi``。車輛超過五台時只取前五個
    再加省略號，免得檔名長到作業系統放不下。
    """
    if codec not in CODECS:
        raise ValueError(f"codec {codec!r} 不在可用清單內：{sorted(CODECS)}")
    suffix = CODECS[codec][1]

    if output_path is not None:
        return Path(output_path).with_suffix(suffix)

    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    tag = ""
    if vehicle_ids:
        names = [str(item) for item in vehicle_ids]
        shown = "-".join(names[:5]) + ("-etc" if len(names) > 5 else "")
        tag = f"_id{shown}"
    source = Path(input_path)
    return source.with_name(f"{source.stem}_bbox{tag}_{stamp}{suffix}")


def render_video(
    video_path: str | os.PathLike[str],
    tracks: pd.DataFrame,
    *,
    style: BoxStyle,
    output_path: str | os.PathLike[str] | None = None,
    start_frame: int | None = None,
    end_frame: int | None = None,
    frame_offset: int = 0,
    codec: str = "MJPG",
    out_scale: float = 1.0,
    show_frame_number: bool = False,
    progress: Callable[[int, int], None] | None = None,
    cancel: threading.Event | None = None,
) -> RenderResult:
    """把軌跡疊到影片上，輸出成新的影片檔。

    Parameters
    ----------
    video_path : str or path-like
        來源影片。
    tracks : pandas.DataFrame
        要畫的車輛，逐影格一列，需含 ``vehicle_id``、``frame`` 與四角點。
        **這張表就是選取結果**——不想畫的車先自己濾掉。
    style : BoxStyle
        外觀設定，顏色表必須涵蓋 tracks 裡的所有車輛。
    output_path : str or path-like, optional
        輸出路徑；副檔名會依 codec 修正。省略時自動命名。
    start_frame, end_frame : int, optional
        要輸出的影格範圍（兩端都含）。省略時用 tracks 的涵蓋範圍；
        tracks 是空的就輸出整部影片。超出影片長度的部分會被夾掉。
    frame_offset : int, optional
        軌跡與影片不同步時的整體平移：``影片影格 = 軌跡影格 + frame_offset``。
        預設 0。
    codec : str, optional
        見 :data:`CODECS`。預設 ``"MJPG"``。
    out_scale : float, optional
        輸出解析度比例，``0.5`` 為長寬各半。**框是在原始解析度上畫完才縮放**，
        線條與文字才不會糊掉。預設 1.0。
    show_frame_number : bool, optional
        左上角疊上影格編號與秒數。預設 False。
    progress : callable, optional
        ``progress(已寫入, 總數)``，每寫完一格呼叫一次。
    cancel : threading.Event, optional
        設定之後會在下一格停止，已寫出的部分保留。

    Returns
    -------
    RenderResult
        實際輸出的範圍、影格數，以及哪些車有畫到、哪些車在這段時間沒有軌跡。

    Raises
    ------
    FileNotFoundError
        來源影片不存在。
    ValueError
        影片打不開、影格範圍無效、codec 不支援、out_scale 不是正數，
        或輸出檔建立失敗。

    Notes
    -----
    **被取消或中途失敗時，已經寫出去的影格會留在檔案裡**，
    ``RenderResult.is_complete`` 會是 False。半截的影片比沒有影片好
    除錯，所以不自動刪除。

    軌跡取樣率低於影片幀率時，中間的影格沒有資料，框會一閃一閃；
    先用 :func:`~traffickit_viz.resample_tracks` 補上再進來。

    本函式**不 print**。要顯示進度請用 ``progress``，要顯示結果請讀回傳值。
    """
    info = probe_video(video_path)
    _check_render_options(codec, out_scale)
    _check_tracks(tracks)

    tracks = tracks.copy()
    tracks["frame"] = tracks["frame"].to_numpy(dtype=np.int64) + int(frame_offset)

    start, end = _resolve_range(tracks, info, start_frame, end_frame)
    wanted = tuple(dict.fromkeys(tracks["vehicle_id"].astype(str)))
    in_range = tracks[tracks["frame"].between(start, end)]
    drawn = tuple(dict.fromkeys(in_range["vehicle_id"].astype(str)))
    missing = tuple(name for name in wanted if name not in set(drawn))

    by_frame = {int(frame): group for frame, group in in_range.groupby("frame")}

    destination = resolve_output_path(
        info.path, output_path, codec=codec, vehicle_ids=drawn
    )
    width = max(1, int(info.width * out_scale))
    height = max(1, int(info.height * out_scale))
    needs_resize = (width, height) != (info.width, info.height)

    capture = cv2.VideoCapture(str(info.path))
    writer = cv2.VideoWriter(
        str(destination), cv2.VideoWriter_fourcc(*CODECS[codec][0]),
        info.fps, (width, height),
    )
    total = end - start + 1
    written = 0
    cancelled = False

    try:
        if not capture.isOpened():
            raise ValueError(f"無法開啟影片：{info.path}")
        if not writer.isOpened():
            raise ValueError(
                f"無法建立輸出影片 {destination}（codec {codec} 可能不被支援）"
            )

        # 直接跳到起始影格，不從頭逐格解碼。
        capture.set(cv2.CAP_PROP_POS_FRAMES, start)
        for offset in range(total):
            if cancel is not None and cancel.is_set():
                cancelled = True
                break
            ok, image = capture.read()
            if not ok:
                break   # 影片比宣告的短；已寫出的部分保留

            frame_number = start + offset
            boxes = by_frame.get(frame_number)
            if boxes is not None:
                draw_boxes(image, boxes, style=style)
            if show_frame_number:
                _draw_frame_number(image, frame_number, info.fps)
            if needs_resize:
                image = cv2.resize(
                    image, (width, height), interpolation=cv2.INTER_AREA
                )

            writer.write(image)
            written += 1
            if progress is not None:
                progress(written, total)
    finally:
        capture.release()
        writer.release()

    return RenderResult(
        output_path=destination,
        start_frame=start,
        end_frame=end,
        frames_written=written,
        drawn_vehicle_ids=drawn,
        missing_vehicle_ids=missing,
        cancelled=cancelled,
    )


def _draw_frame_number(image, frame_number: int, fps: float) -> None:
    text = f"frame {frame_number}  t={frame_number / fps:.2f}s"
    # 先粗黑再細白，這樣不管底下畫面是亮是暗都讀得到。
    for color, thickness in (((0, 0, 0), 4), ((255, 255, 255), 1)):
        cv2.putText(
            image, text, _OVERLAY_ORIGIN, cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            color, thickness, cv2.LINE_AA,
        )


def _check_render_options(codec: str, out_scale: float) -> None:
    if codec not in CODECS:
        raise ValueError(f"codec {codec!r} 不在可用清單內：{sorted(CODECS)}")
    if not isinstance(out_scale, (int, float)) or isinstance(out_scale, bool):
        raise ValueError(f"out_scale 必須是數字，收到 {out_scale!r}")
    if not np.isfinite(out_scale) or out_scale <= 0:
        raise ValueError(f"out_scale 必須是有限的正數，收到 {out_scale}")


def _check_tracks(tracks) -> None:
    if not isinstance(tracks, pd.DataFrame):
        raise TypeError(
            f"tracks 必須是 pandas.DataFrame，收到 {type(tracks).__name__}"
        )
    for name in ("vehicle_id", "frame"):
        if name not in tracks.columns:
            raise ValueError(f"tracks 缺少必要欄位：{name}")


def _resolve_range(
    tracks: pd.DataFrame,
    info: VideoInfo,
    start_frame: int | None,
    end_frame: int | None,
) -> tuple[int, int]:
    last = max(0, info.frame_count - 1)

    if start_frame is None or end_frame is None:
        if tracks.empty:
            span = (0, last)
        else:
            frames = tracks["frame"].to_numpy()
            span = (int(frames.min()), int(frames.max()))
        start_frame = span[0] if start_frame is None else start_frame
        end_frame = span[1] if end_frame is None else end_frame

    start = int(start_frame)
    end = int(end_frame)
    if start < 0:
        raise ValueError(f"start_frame 不可以是負數，收到 {start}")
    if end < start:
        raise ValueError(f"end_frame（{end}）早於 start_frame（{start}）")
    if info.frame_count > 0 and start > last:
        raise ValueError(
            f"start_frame {start} 超出影片範圍（0 ~ {last}）"
        )
    # 結尾超出就夾掉：軌跡比影片長一點是常見的資料誤差，不值得擋下整次輸出。
    return start, min(end, last) if info.frame_count > 0 else end


def iter_frame_numbers(start: int, end: int) -> Iterable[int]:
    """``[start, end]`` 的影格編號，兩端都含。"""
    return range(start, end + 1)
