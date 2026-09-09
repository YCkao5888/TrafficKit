"""車速分布統計的內部實作。

公開入口是 ``traffickit.speed.summarise_speed_distribution``；
本檔案的其他名稱不保證穩定。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from .._validation import (
    check_label_column,
    check_nonnegative_column,
    check_real,
    check_unique,
    require_columns,
    require_dataframe,
)

_REQUIRED = ("vehicle_id", "time_s", "speed_smooth_mps")

_STATISTICS = ("mean", "median", "max", "p85")

_VEHICLE_DTYPES = {
    "vehicle_id": "string",
    "sample_count": "int64",
    "speed_mps": "float64",
}

_BIN_DTYPES = {
    "bin_index": "int64",
    "lower_mps": "float64",
    "upper_mps": "float64",
    "vehicle_count": "int64",
    "proportion": "float64",
}

# 邊界以 start + i * width 計算後四捨五入的位數。
# 只用來吸收浮點累積誤差，不是給使用者調整的精度設定。
_EDGE_DECIMALS = 9


@dataclass(frozen=True)
class SpeedSummary:
    """每車代表速度的整體統計，單位 m/s。

    統計母體是 :attr:`SpeedDistribution.vehicle_speeds`，也就是通過
    ``moving_threshold_mps`` 後仍有樣本的所有車輛，**包含落在分箱範圍
    之外的車輛**。

    車輛數為 0 時所有統計量為 ``None``；車輛數為 1 時 ``std_mps`` 也是
    ``None``：樣本標準差未定義，不以 0 代替。
    """

    vehicle_count: int
    mean_mps: Optional[float]
    std_mps: Optional[float]
    min_mps: Optional[float]
    median_mps: Optional[float]
    p85_mps: Optional[float]
    max_mps: Optional[float]


@dataclass(frozen=True)
class SpeedDistribution:
    """車速分布統計結果。

    Attributes
    ----------
    bins : pandas.DataFrame
        一列一個分箱：bin_index、lower_mps、upper_mps、vehicle_count、
        proportion。proportion 的分母是 ``binned_vehicle_count``；分母
        為 0 時所有 proportion 為 0.0。
    vehicle_speeds : pandas.DataFrame
        一列一台車：vehicle_id、sample_count、speed_mps。依 vehicle_id
        字串排序。呼叫端可用它自行畫箱形圖或分車種彙整。
    summary : SpeedSummary
        ``vehicle_speeds`` 的整體統計。
    statistic : str
        本次採用的每車代表速度統計量。
    moving_threshold_mps : float or None
        本次採用的樣本層移動門檻；None 表示未過濾。
    input_vehicle_count : int
        套用移動門檻**之前**的車輛數。
    binned_vehicle_count : int
        落在分箱範圍內的車輛數，即直方圖分母。
    below_range_count, above_range_count : int
        代表速度低於第一個邊界、或高於最後一個邊界的車輛數。三者相加
        等於 ``summary.vehicle_count``。
    """

    bins: pd.DataFrame
    vehicle_speeds: pd.DataFrame
    summary: SpeedSummary
    statistic: str
    moving_threshold_mps: Optional[float]
    input_vehicle_count: int
    binned_vehicle_count: int
    below_range_count: int
    above_range_count: int


def speed_bin_edges(
    width_mps: float,
    upper_mps: float,
    *,
    start_mps: float = 0.0,
) -> tuple[float, ...]:
    """產生等寬的分箱邊界，最後一個邊界不小於 ``upper_mps``。

    多個群組（例如機車與汽車）要畫在同一張圖時，呼叫端應先用整體資料
    算出一組邊界，再把同一組邊界傳給每一次
    :func:`summarise_speed_distribution`，否則各組的分箱不可比較。

    Parameters
    ----------
    width_mps : float
        分箱寬度，有限且大於 0。
    upper_mps : float
        要涵蓋的上限，有限且不小於 ``start_mps``。
    start_mps : float, optional
        第一個邊界，有限且非負，預設 0.0。

    Returns
    -------
    tuple of float
        至少兩個嚴格遞增的邊界值。

    Raises
    ------
    ValueError
        參數不是有限實數，或不符合上述範圍。
    """
    start = check_real("start_mps", start_mps, minimum=0.0)
    width = check_real(
        "width_mps", width_mps, minimum=0.0, allow_minimum=False
    )
    upper = check_real("upper_mps", upper_mps, minimum=start)

    count = max(1, ceil((upper - start) / width))
    return tuple(
        round(start + index * width, _EDGE_DECIMALS)
        for index in range(count + 1)
    )


def summarise_speed_distribution(
    tracks: pd.DataFrame,
    *,
    bin_edges_mps: Iterable[float],
    statistic: str = "mean",
    moving_threshold_mps: Optional[float] = None,
) -> SpeedDistribution:
    """統計每車代表速度的分布。

    先把每台車的樣本收斂成一個代表速度，再依給定邊界分箱。分箱與統計
    的對象都是「車」，不是「樣本」，所以停留較久的車不會被重複計數。

    Parameters
    ----------
    tracks : pandas.DataFrame
        單一資料集的樣本。必要欄位：vehicle_id（非空白字串）、time_s
        （共同起點的非負秒數）、speed_smooth_mps（非負 m/s，已完成
        平滑）。數值須有限、無缺值；(vehicle_id, time_s) 不可重複。
        允許未排序或含額外欄位；不修改輸入。
    bin_edges_mps : iterable of float
        至少兩個、嚴格遞增、有限且非負的邊界，單位 m/s。分箱為
        ``[lower, upper)``，最後一箱為 ``[lower, upper]``。不提供預設
        邊界，避免呼叫端忘記設定時套用不適用的分箱。
    statistic : {'mean', 'median', 'max', 'p85'}, optional
        每車代表速度的取法，預設 'mean'。'p85' 為該車樣本的 85 百分位，
        採 pandas 預設的線性內插。
    moving_threshold_mps : float or None, optional
        樣本層移動門檻，單位 m/s。給定時只保留 ``speed_smooth_mps``
        大於門檻的樣本，**比較是嚴格大於，等於門檻不算**。
        過濾後沒有樣本的車輛整台排除；預設 None 表示不過濾。

    Returns
    -------
    SpeedDistribution
        分箱結果、每車代表速度、整體統計與各項分母。

    Raises
    ------
    TypeError
        tracks 不是 DataFrame。
    ValueError
        欄位、數值、ID、重複樣本或參數不符合輸入規格。

    Notes
    -----
    本函式不進行速度平滑、單位換算、ROI 或時間裁切，也不讀寫檔案。
    像素／公尺比例尺換算、km/h 顯示、車種分組與時段篩選由呼叫端處理；
    要分車種比較時，請自行切好子集合並沿用同一組 ``bin_edges_mps``。
    """
    require_dataframe(tracks, "tracks")

    edges = _check_bin_edges(bin_edges_mps)
    if statistic not in _STATISTICS:
        raise ValueError(f"statistic 必須是 {list(_STATISTICS)} 其中之一")
    if moving_threshold_mps is not None:
        moving_threshold_mps = check_real(
            "moving_threshold_mps", moving_threshold_mps, minimum=0.0
        )

    work = _validated_samples(tracks)
    input_vehicle_count = int(work["vehicle_id"].nunique())

    if moving_threshold_mps is not None:
        work = work.loc[work["speed_smooth_mps"] > moving_threshold_mps]

    vehicle_speeds = _aggregate_per_vehicle(work, statistic)
    bins, binned, below, above = _bin_vehicles(vehicle_speeds, edges)

    return SpeedDistribution(
        bins=bins,
        vehicle_speeds=vehicle_speeds,
        summary=_summarise(vehicle_speeds["speed_mps"]),
        statistic=statistic,
        moving_threshold_mps=moving_threshold_mps,
        input_vehicle_count=input_vehicle_count,
        binned_vehicle_count=binned,
        below_range_count=below,
        above_range_count=above,
    )


def _check_bin_edges(bin_edges_mps: Iterable[float]) -> np.ndarray:
    if isinstance(bin_edges_mps, (str, bytes)) or not isinstance(
        bin_edges_mps, Iterable
    ):
        raise ValueError("bin_edges_mps 必須是數值序列")
    edges = [
        check_real(f"bin_edges_mps[{index}]", value, minimum=0.0)
        for index, value in enumerate(bin_edges_mps)
    ]
    if len(edges) < 2:
        raise ValueError("bin_edges_mps 至少需要兩個邊界")
    if any(later <= earlier for earlier, later in zip(edges, edges[1:])):
        raise ValueError("bin_edges_mps 必須嚴格遞增")
    return np.asarray(edges, dtype="float64")


def _validated_samples(tracks: pd.DataFrame) -> pd.DataFrame:
    require_columns(tracks, _REQUIRED, name="tracks")

    # 複製必要欄位，避免修改呼叫端持有的原始資料。
    work = tracks.loc[:, list(_REQUIRED)].copy()
    if work.empty:
        work["vehicle_id"] = work["vehicle_id"].astype("string")
        for column in ("time_s", "speed_smooth_mps"):
            work[column] = work[column].astype("float64")
        return work.reset_index(drop=True)

    check_label_column(work, "vehicle_id")
    for column in ("time_s", "speed_smooth_mps"):
        work[column] = check_nonnegative_column(work, column)

    check_unique(
        work,
        ["vehicle_id", "time_s"],
        message="同一 vehicle_id 與 time_s 不可有重複樣本",
    )
    work["vehicle_id"] = work["vehicle_id"].astype("string")
    return work.reset_index(drop=True)


def _aggregate_per_vehicle(
    work: pd.DataFrame,
    statistic: str,
) -> pd.DataFrame:
    # sort=True 讓輸出依 vehicle_id 字串排序，與輸入是否排序無關。
    grouped = work.groupby("vehicle_id", sort=True)["speed_smooth_mps"]
    if statistic == "mean":
        speeds = grouped.mean()
    elif statistic == "median":
        speeds = grouped.median()
    elif statistic == "max":
        speeds = grouped.max()
    else:
        speeds = grouped.quantile(0.85)

    result = pd.DataFrame({
        "vehicle_id": speeds.index,
        "sample_count": grouped.size().to_numpy(),
        "speed_mps": speeds.to_numpy(),
    })
    return result.astype(_VEHICLE_DTYPES).reset_index(drop=True)


def _bin_vehicles(
    vehicle_speeds: pd.DataFrame,
    edges: np.ndarray,
) -> tuple[pd.DataFrame, int, int, int]:
    bin_count = len(edges) - 1
    values = vehicle_speeds["speed_mps"].to_numpy(dtype="float64")

    indexes = np.searchsorted(edges, values, side="right") - 1
    # 最後一箱含右端點：等於最後一個邊界的值歸入最後一箱。
    indexes = np.where(values == edges[-1], bin_count - 1, indexes)

    below = int((indexes < 0).sum())
    above = int((indexes >= bin_count).sum())
    inside = indexes[(indexes >= 0) & (indexes < bin_count)]
    counts = np.bincount(inside, minlength=bin_count).astype("int64")

    binned = int(counts.sum())
    proportion = (
        counts / binned if binned else np.zeros(bin_count, dtype="float64")
    )

    bins = pd.DataFrame({
        "bin_index": np.arange(bin_count),
        "lower_mps": edges[:-1],
        "upper_mps": edges[1:],
        "vehicle_count": counts,
        "proportion": proportion,
    }).astype(_BIN_DTYPES)
    return bins, binned, below, above


def _summarise(speeds: pd.Series) -> SpeedSummary:
    count = int(speeds.size)
    if count == 0:
        return SpeedSummary(0, None, None, None, None, None, None)
    return SpeedSummary(
        vehicle_count=count,
        mean_mps=float(speeds.mean()),
        # 單車時樣本標準差未定義，回傳 None 而不是 0.0。
        std_mps=float(speeds.std(ddof=1)) if count > 1 else None,
        min_mps=float(speeds.min()),
        median_mps=float(speeds.median()),
        p85_mps=float(speeds.quantile(0.85)),
        max_mps=float(speeds.max()),
    )
