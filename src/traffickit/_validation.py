"""各功能共用的輸入驗證。

只放「兩個以上功能需要相同語意」的檢查。錯誤訊息一律指出欄位或參數名稱，
讓呼叫端不必翻原始碼就知道哪裡不合規格。
"""

from __future__ import annotations

from math import isfinite
from numbers import Real
from typing import Iterable, Sequence

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_complex_dtype,
    is_numeric_dtype,
)


def check_real(
    name: str,
    value: object,
    *,
    minimum: float,
    allow_minimum: bool = True,
) -> float:
    """確認 value 是有限實數並回傳 float。布林值不算數值。"""
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not isfinite(float(value))
    ):
        raise ValueError(f"{name} 必須是有限的實數")
    number = float(value)
    if allow_minimum and number < minimum:
        raise ValueError(f"{name} 必須不小於 {minimum}")
    if not allow_minimum and number <= minimum:
        raise ValueError(f"{name} 必須大於 {minimum}")
    return number


def require_dataframe(value: object, name: str) -> None:
    if not isinstance(value, pd.DataFrame):
        raise TypeError(f"{name} 必須是 pandas.DataFrame")


def require_columns(
    frame: pd.DataFrame,
    required: Sequence[str],
    *,
    name: str,
) -> None:
    if frame.columns.duplicated().any():
        raise ValueError(f"{name} 不可包含重複欄名")
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{name} 缺少必要欄位：{missing}")


def check_label_column(frame: pd.DataFrame, column: str) -> None:
    """確認欄位每一格都是非空白字串。"""
    valid = frame[column].map(
        lambda value: isinstance(value, str) and bool(value.strip())
    )
    if not valid.all():
        raise ValueError(f"{column} 必須是非空白字串且不可缺值")


def check_nonnegative_column(frame: pd.DataFrame, column: str) -> pd.Series:
    """確認欄位是有限、非負的實數欄位，回傳 float64 版本。"""
    values = frame[column]
    if (
        not is_numeric_dtype(values.dtype)
        or is_bool_dtype(values.dtype)
        or is_complex_dtype(values.dtype)
    ):
        raise ValueError(f"{column} 必須是實數欄位，不接受數字字串")
    if values.isna().any():
        raise ValueError(f"{column} 不可有缺值")
    if not values.map(isfinite).all() or (values < 0).any():
        raise ValueError(f"{column} 必須是有限且非負的數值")
    return values.astype("float64")


def check_unique(
    frame: pd.DataFrame,
    columns: Iterable[str],
    *,
    message: str,
) -> None:
    """確認指定欄位組合沒有重複列；message 是完整的錯誤訊息。"""
    if frame.duplicated(list(columns)).any():
        raise ValueError(message)
