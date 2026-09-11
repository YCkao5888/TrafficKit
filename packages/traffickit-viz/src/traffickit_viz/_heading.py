"""由四角點推出車頭方向，並沿時間平滑。

角點順序的約定來自 ``traffickit.formats``：前兩點是車頭兩角、後兩點是車尾
兩角。車頭方向就是「車頭中點減車尾中點」。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: 逐影格四角點的欄位名稱，與 ``traffickit.formats.read_motc_su_tracks`` 一致。
CORNER_COLUMNS = (
    "x1_px", "y1_px", "x2_px", "y2_px", "x3_px", "y3_px", "x4_px", "y4_px",
)

_EPSILON = 1e-9


def add_headings(
    tracks: pd.DataFrame,
    *,
    window: int = 5,
    order_by: str = "frame",
) -> pd.DataFrame:
    """替逐影格軌跡加上平滑後的車頭方向。

    Parameters
    ----------
    tracks : pandas.DataFrame
        一列一台車一個時間點，需含 ``vehicle_id``、四角點欄位
        （``x1_px``…``y4_px``）與 ``order_by`` 指定的欄位。
        通常直接來自 :func:`traffickit.formats.read_motc_su_tracks`。
    window : int, optional
        平滑範圍：取前後各 ``window`` 格的平均方向。0 表示不平滑，
        直接用單格的方向。預設 5。
    order_by : str, optional
        排序依據的欄位名稱，決定「前後幾格」是哪幾列。預設 ``"frame"``；
        沒有影格編號時（例如 SSAM 版）傳 ``"time_s"``。

    Returns
    -------
    pandas.DataFrame
        輸入的副本，**依原本的列順序**多出兩欄：``heading_x``、``heading_y``，
        是單位向量。方向無法決定時是 ``NaN``，不是 0。

    Raises
    ------
    TypeError
        tracks 不是 DataFrame。
    ValueError
        缺必要欄位，或 window 是負數。

    Notes
    -----
    **為什麼要平滑。** 車頭那條邊是偵測框的一部分，框抖它就跟著抖；
    直接用單格方向畫箭頭，箭頭會一直晃。取前後數格的單位向量平均之後，
    抖動大約降到十分之一。

    平均的是**單位向量**不是原始向量，否則車身長度不同的影格權重會不一樣。

    車頭與車尾中點重合的影格算不出方向，該列回 ``NaN``；平均時也會跳過
    這些格，不會把它們當成 0 拉偏結果。整段都算不出來的車輛整欄是 ``NaN``。

    本函式**不修改輸入**，也不重新排序輸出。
    """
    if not isinstance(tracks, pd.DataFrame):
        raise TypeError(f"tracks 必須是 pandas.DataFrame，收到 {type(tracks).__name__}")
    if not isinstance(window, int) or isinstance(window, bool):
        raise ValueError(f"window 必須是整數，收到 {window!r}")
    if window < 0:
        raise ValueError(f"window 不可以是負數，收到 {window}")

    required = ("vehicle_id", order_by, *CORNER_COLUMNS)
    missing = [name for name in required if name not in tracks.columns]
    if missing:
        raise ValueError(f"tracks 缺少必要欄位：{missing}")

    result = tracks.copy()
    heading = np.full((len(result), 2), np.nan)

    if len(result):
        # 用位置而不是索引：軌跡表允許重複的列索引。
        order = np.argsort(
            result[order_by].to_numpy(), kind="stable"
        )
        vehicle_ids = result["vehicle_id"].to_numpy()
        corners = result.loc[:, list(CORNER_COLUMNS)].to_numpy(dtype="float64")

        for positions in _groups_in_order(vehicle_ids, order):
            heading[positions] = _smoothed_unit_headings(
                corners[positions], window
            )

    result["heading_x"] = heading[:, 0]
    result["heading_y"] = heading[:, 1]
    return result


def _groups_in_order(vehicle_ids: np.ndarray, order: np.ndarray):
    """依車輛分組，每組回傳一個「已依 order_by 排好」的位置陣列。"""
    grouped: dict[object, list[int]] = {}
    for position in order:
        grouped.setdefault(vehicle_ids[position], []).append(position)
    for positions in grouped.values():
        yield np.asarray(positions, dtype=np.intp)


def _smoothed_unit_headings(corners: np.ndarray, window: int) -> np.ndarray:
    """corners (n, 8) → 平滑後的單位方向 (n, 2)，算不出來的列是 NaN。"""
    points = corners.reshape(-1, 4, 2)
    raw = points[:, :2].mean(axis=1) - points[:, 2:].mean(axis=1)

    norms = np.linalg.norm(raw, axis=1)
    usable = norms > _EPSILON
    units = np.zeros_like(raw)
    units[usable] = raw[usable] / norms[usable, None]

    if window == 0:
        smoothed = units.copy()
        counts = usable.astype(np.int64)
    else:
        # 前綴和讓視窗平均是 O(n)，不必對每一格重新切片相加。
        total = np.vstack(([[0.0, 0.0]], np.cumsum(units, axis=0)))
        seen = np.concatenate(([0], np.cumsum(usable)))
        count = len(units)
        low = np.maximum(np.arange(count) - window, 0)
        high = np.minimum(np.arange(count) + window + 1, count)
        smoothed = total[high] - total[low]
        counts = seen[high] - seen[low]

    result = np.full_like(raw, np.nan)
    has_samples = counts > 0
    if has_samples.any():
        mean = smoothed[has_samples] / counts[has_samples, None]
        lengths = np.linalg.norm(mean, axis=1)
        # 方向互相抵銷（例如原地打轉）時長度趨近 0，方向沒有意義，留 NaN。
        defined = lengths > _EPSILON
        rows = np.flatnonzero(has_samples)[defined]
        result[rows] = mean[defined] / lengths[defined, None]
    return result
