"""把軌跡取樣到影片的影格上。

軌跡的取樣率常常低於影片幀率（例如軌跡 9.99 fps、影片 29.97 fps），
中間的影格沒有資料，框就會一閃一閃。這一層用線性內插補上。

**補框是畫面決定，不是交通判定**：補出來的位置只是為了讓框跟著車，不會
回寫到任何統計。要算速度或轉向，請用原始取樣點。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ._heading import CORNER_COLUMNS

#: 內插後會重算的欄位，不從輸入沿用。
_RECOMPUTED = ("center_x_px", "center_y_px")

#: 內插後沒有意義、直接丟掉的欄位。
_DROPPED = ("time_s", "heading_x", "heading_y")


def resample_tracks(
    tracks: pd.DataFrame,
    frames,
    *,
    interpolate: bool = True,
    max_gap: int = 30,
) -> pd.DataFrame:
    """把逐影格軌跡重新取樣到指定的影格上。

    Parameters
    ----------
    tracks : pandas.DataFrame
        逐影格軌跡，需含 ``vehicle_id``、``frame`` 與四角點欄位。
    frames : array-like of int
        要取樣到哪些影格，通常是 ``range(start, end + 1)``。
    interpolate : bool, optional
        取樣點之間要不要線性內插。``False`` 時只保留剛好對上的影格。
        預設 True。
    max_gap : int, optional
        內插允許的最大取樣間隔（影格）。相鄰兩個取樣點相距超過這個值時，
        中間**不補**。預設 30。

    Returns
    -------
    pandas.DataFrame
        依 ``vehicle_id``、``frame`` 排序。欄位為 ``vehicle_id``、``frame``、
        四角點、``center_x_px``、``center_y_px``，外加輸入裡**每台車固定不變**
        的欄位（例如 ``vehicle_class``、``is_complete``）。

    Raises
    ------
    TypeError
        tracks 不是 DataFrame。
    ValueError
        缺必要欄位、max_gap 是負數，或某個應為固定值的欄位在同一台車內不一致。

    Notes
    -----
    **``max_gap`` 是在防「車子早就開走了框還留著」。** 車輛被遮蔽或離開畫面
    時，軌跡會中斷；若不限制間隔，內插會把中斷前後兩點連成一條直線，於是
    畫面上出現一個憑空滑過去的框。相距超過 ``max_gap`` 的區段不補，
    寧可讓框消失。

    **實際有取樣到的影格一律保留**，不受 ``max_gap`` 影響——要擋的是補出來
    的框，不是真的偵測結果。因此 ``max_gap=0`` 等同 ``interpolate=False``。
    舊工具在這裡會把寬間隔兩端的真實取樣點也一併丟掉，本函式不照抄。

    ``time_s`` 與 ``heading_x``／``heading_y`` **不會出現在輸出**：前者要由
    影片幀率決定，後者內插後需要重新正規化。**順序是先重新取樣、
    再呼叫** :func:`~traffickit_viz.add_headings`。

    本函式不修改輸入。
    """
    if not isinstance(tracks, pd.DataFrame):
        raise TypeError(
            f"tracks 必須是 pandas.DataFrame，收到 {type(tracks).__name__}"
        )
    if max_gap < 0:
        raise ValueError(f"max_gap 不可以是負數，收到 {max_gap}")

    required = ("vehicle_id", "frame", *CORNER_COLUMNS)
    missing = [name for name in required if name not in tracks.columns]
    if missing:
        raise ValueError(f"tracks 缺少必要欄位：{missing}")

    targets = np.unique(np.asarray(frames, dtype=np.int64))
    carried = _carried_columns(tracks)

    pieces = []
    if targets.size:
        for vehicle_id, group in tracks.groupby("vehicle_id", sort=True):
            piece = _resample_one(
                group, targets, interpolate=interpolate, max_gap=max_gap,
                carried=carried,
            )
            if piece is not None:
                pieces.append(piece)

    columns = ["vehicle_id", "frame", *CORNER_COLUMNS, *_RECOMPUTED, *carried]
    if not pieces:
        return pd.DataFrame({name: pd.Series(dtype=tracks[name].dtype)
                             if name in tracks.columns
                             else pd.Series(dtype="float64")
                             for name in columns})

    result = pd.concat(pieces, ignore_index=True)
    return result.loc[:, columns]


def _carried_columns(tracks: pd.DataFrame) -> list[str]:
    """挑出可以原樣沿用的欄位：每台車內都是同一個值的那些。"""
    skip = {"vehicle_id", "frame", *CORNER_COLUMNS, *_RECOMPUTED, *_DROPPED}
    candidates = [name for name in tracks.columns if name not in skip]
    if not candidates or tracks.empty:
        return candidates

    counts = tracks.groupby("vehicle_id", sort=False)[candidates].nunique(
        dropna=False
    )
    varying = [name for name in candidates if (counts[name] > 1).any()]
    if varying:
        raise ValueError(
            f"欄位 {varying} 在同一台車內有多個值，無法沿用到內插出來的影格。"
            f"請先移除這些欄位，或確認資料是否錯位"
        )
    return candidates


def _resample_one(group, targets, *, interpolate, max_gap, carried):
    ordered = group.sort_values("frame", kind="stable")
    source = ordered["frame"].to_numpy(dtype=np.int64)
    corners = ordered.loc[:, list(CORNER_COLUMNS)].to_numpy(dtype="float64")

    if source.size == 0:
        return None

    if not interpolate or source.size == 1:
        hit = targets[np.isin(targets, source)]
        if hit.size == 0:
            return None
        values = corners[np.searchsorted(source, hit)]
    else:
        inside = (targets >= source[0]) & (targets <= source[-1])
        hit = targets[inside]
        if hit.size == 0:
            return None

        # 每個目標影格落在哪一段取樣區間；跨距超過 max_gap 的區段不補。
        left = np.clip(
            np.searchsorted(source, hit, side="right") - 1, 0, source.size - 2
        )
        within_gap = (source[left + 1] - source[left]) <= max_gap
        # 真的有取樣到的影格一律保留：max_gap 要擋的是「補出來的框」，
        # 不是實際的偵測結果。落在寬間隔兩端的那兩格仍然是真資料。
        hit = hit[within_gap | np.isin(hit, source)]
        if hit.size == 0:
            return None

        values = np.empty((hit.size, len(CORNER_COLUMNS)))
        for column in range(len(CORNER_COLUMNS)):
            values[:, column] = np.interp(hit, source, corners[:, column])

    piece = pd.DataFrame(values, columns=list(CORNER_COLUMNS))
    piece.insert(0, "vehicle_id", ordered["vehicle_id"].iloc[0])
    piece.insert(1, "frame", hit)
    piece["center_x_px"] = values[:, 0::2].mean(axis=1)
    piece["center_y_px"] = values[:, 1::2].mean(axis=1)
    for name in carried:
        piece[name] = ordered[name].iloc[0]
    return piece
