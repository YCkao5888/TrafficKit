"""時間寫法與影格編號的互轉。

輸出一段影片時，人習慣說「從 1 分 30 秒開始」或「事發前後各 5 秒」，
但 OpenCV 只認影格編號。這一層負責翻譯，不做任何交通判定。
"""

from __future__ import annotations

import math

import pandas as pd


def parse_time_spec(spec: str | int | float, fps: float) -> int:
    """把時間寫法轉成影格編號。

    Parameters
    ----------
    spec : str, int or float
        接受四種寫法：影格編號（``"950"`` 或 ``950``）、秒數（``"12.5s"``）、
        時分秒（``"00:01:30"``、``"01:30"``、``"00:01:30.5"``）。
        沒有單位就當成影格編號。
    fps : float
        影片幀率，用來把秒換算成影格。必須有限且大於 0。

    Returns
    -------
    int
        影格編號，四捨五入到整數。

    Raises
    ------
    ValueError
        寫法無法解析，或 fps 無效。

    Notes
    -----
    **``"10"`` 是第 10 格，``"10s"`` 是第 10 秒**——差一個字母差很多。
    這個歧義來自舊工具的命令列介面，為了讓習慣的人不必改寫法而保留；
    程式呼叫時建議直接傳整數，意思最清楚。

    時分秒容許超過 60 的分鐘或秒數（``"0:90"`` 就是 90 秒），
    因為那通常是人手算出來的，擋掉只會讓人多算一次。
    """
    _check_fps(fps)

    if isinstance(spec, bool):
        raise ValueError(f"無法解析時間 {spec!r}")
    if isinstance(spec, (int, float)):
        if not math.isfinite(spec):
            raise ValueError(f"無法解析時間 {spec!r}，不是有限數值")
        return int(round(spec))

    if not isinstance(spec, str):
        raise ValueError(
            f"時間必須是字串或數字，收到 {type(spec).__name__}"
        )

    text = spec.strip()
    if not text:
        raise ValueError("時間不可以是空白")

    try:
        if ":" in text:
            parts = text.split(":")
            if len(parts) > 3:
                raise ValueError("最多只能有 時:分:秒 三段")
            seconds = 0.0
            for part in parts:
                seconds = seconds * 60 + float(part)
            return int(round(seconds * fps))

        if text[-1].lower() == "s":
            return int(round(float(text[:-1]) * fps))

        return int(round(float(text)))
    except ValueError as error:
        raise ValueError(
            f"無法解析時間 {spec!r}（{error}）。"
            f"可用寫法：影格 123、秒數 12.5s、或 00:01:30"
        ) from None


def resolve_center_range(
    center: int,
    before: int,
    after: int,
    *,
    total_frames: int | None = None,
) -> tuple[int, int]:
    """以某個時間點為中心，往前後各取一段，回傳 ``(起, 迄)``（兩端都含）。

    Parameters
    ----------
    center : int
        中心影格。
    before, after : int
        往前、往後各幾格。負數視為 0。前後可以不對稱。
    total_frames : int, optional
        影片總格數。給了就把結果夾在 ``0`` 到 ``total_frames - 1`` 之間。

    Returns
    -------
    tuple of int
        ``(start, end)``，保證 ``end >= start``。

    Notes
    -----
    衝突事件通常是說「事發前 2 秒到後 4 秒」，用中心點加前後長度比起訖好抓。
    **超出影片範圍的部分直接夾掉，不當成錯誤**——事件發生在影片開頭或結尾
    附近是常態，為此拋錯只會讓呼叫端每次都要自己夾一次。
    """
    start = center - max(before, 0)
    end = center + max(after, 0)

    start = max(0, start)
    if total_frames is not None:
        if total_frames < 1:
            raise ValueError(f"total_frames 必須至少是 1，收到 {total_frames}")
        start = min(start, total_frames - 1)
        end = min(end, total_frames - 1)
    return start, max(start, end)


def frame_span(
    tracks: pd.DataFrame,
    *,
    vehicle_ids=None,
    pad: int = 0,
) -> tuple[int, int] | None:
    """這些車輛出現的影格範圍（聯集），沒有任何一格就回 ``None``。

    Parameters
    ----------
    tracks : pandas.DataFrame
        逐影格軌跡，需含 ``vehicle_id`` 與 ``frame``。
    vehicle_ids : iterable, optional
        只看這些車；預設看全部。
    pad : int, optional
        前後各多留幾格。起點不會小於 0。預設 0。

    Returns
    -------
    tuple of int or None
        ``(start, end)``，兩端都含。
    """
    missing = [name for name in ("vehicle_id", "frame") if name not in tracks.columns]
    if missing:
        raise ValueError(f"tracks 缺少必要欄位：{missing}")
    if pad < 0:
        raise ValueError(f"pad 不可以是負數，收到 {pad}")

    if vehicle_ids is not None:
        wanted = {str(item) for item in vehicle_ids}
        tracks = tracks[tracks["vehicle_id"].astype(str).isin(wanted)]
    if tracks.empty:
        return None

    frames = tracks["frame"].to_numpy()
    return max(0, int(frames.min()) - pad), int(frames.max()) + pad


def _check_fps(fps: float) -> None:
    if not isinstance(fps, (int, float)) or isinstance(fps, bool):
        raise ValueError(f"fps 必須是數字，收到 {fps!r}")
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError(f"fps 必須是有限的正數，收到 {fps}")
