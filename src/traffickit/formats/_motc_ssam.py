"""MOTC_SSAM 空拍影像軌跡檔的讀取。

公開入口是 ``traffickit.formats`` 匯出的名稱；本檔案的其他名稱不保證穩定。

本模組屬於**格式轉換層**：只把檔案內容轉成套件契約的欄位與型別，
不做任何交通判定（不推轉向、不算速度、不裁時段、不排除任何車輛）。

與 :mod:`._motc_su` 讀的是同一批空拍影像分析成果的**另一種輸出版本**：
Pixel Frame 版一列一台車、座標是像素；SSAM 版一列一台車一個時間步、
座標是公尺，車身以車頭中點、車尾中點與車寬表示。路口代號與車種代號
兩版完全相同，共用 :mod:`._motc_common` 的定義。
"""

from __future__ import annotations

import csv
import os
from typing import Iterator

import numpy as np
import pandas as pd

from . import _motc_common

#: 表頭列的第一個欄位。SSAM 檔開頭有 FORMAT／DIMENSIONS 等區塊，
#: 找到這一列才算進入資料區。
_HEADER_MARKER = "timestep"

# 輸出欄位名 → 表頭欄位名（比對時一律去空白並轉小寫）。
_NUMERIC_FIELDS = (
    ("front_x_m", "front x"),
    ("front_y_m", "front y"),
    ("rear_x_m", "rear x"),
    ("rear_y_m", "rear y"),
    ("length_m", "length"),
    ("width_m", "width"),
)
_TEXT_FIELDS = (
    ("vehicle_id", "vehicle id"),
    ("vehicle_class", "class"),
    ("entry_code", "intersection in"),
    ("exit_code", "intersection out"),
)
_TIME_FIELD = ("time_s", "timestep")

_CORNER_COLUMNS = tuple(
    f"{axis}{index}_m" for index in range(1, 5) for axis in ("x", "y")
)

_VEHICLE_DTYPES = {
    "vehicle_id": "string",
    "entry_gate": "string",
    "exit_gate": "string",
    "vehicle_class": "string",
    "entry_time_s": "float64",
    "exit_time_s": "float64",
    "sample_count": "int64",
    "is_complete": "bool",
    "is_crosswalk": "bool",
}

_TRACK_DTYPES = {
    "vehicle_id": "string",
    "time_s": "float64",
    "front_x_m": "float64",
    "front_y_m": "float64",
    "rear_x_m": "float64",
    "rear_y_m": "float64",
    "length_m": "float64",
    "width_m": "float64",
    **{name: "float64" for name in _CORNER_COLUMNS},
    "center_x_m": "float64",
    "center_y_m": "float64",
    "is_complete": "bool",
    "is_crosswalk": "bool",
}


class _Vehicle:
    """同一個 vehicle_id 在檔案中所有列的彙整，只在本模組內流通。"""

    __slots__ = ("vehicle_id", "entry_gate", "exit_gate", "entry_kind",
                 "exit_kind", "vehicle_class", "first_time_s", "last_time_s",
                 "sample_count", "times", "line_no")

    def __init__(self, vehicle_id, entry_gate, exit_gate, entry_kind, exit_kind,
                 vehicle_class, time_s, line_no):
        self.vehicle_id = vehicle_id
        self.entry_gate = entry_gate
        self.exit_gate = exit_gate
        self.entry_kind = entry_kind
        self.exit_kind = exit_kind
        self.vehicle_class = vehicle_class
        self.first_time_s = time_s
        self.last_time_s = time_s
        self.sample_count = 1
        self.times = {time_s}
        self.line_no = line_no

    @property
    def is_complete(self) -> bool:
        return _motc_common.INCOMPLETE not in (self.entry_kind, self.exit_kind)

    @property
    def is_crosswalk(self) -> bool:
        return _motc_common.CROSSWALK in (self.entry_kind, self.exit_kind)

    def add(self, entry_gate, exit_gate, vehicle_class, time_s, line_no) -> None:
        # 同一台車的進出代號與車種在整份檔案裡應該是固定的。不一致代表
        # ID 被重複使用或檔案錯位，兩者都會讓下游的轉向流量算錯，要擋下來。
        self._require_same("進入路口代號", self.entry_gate, entry_gate, line_no)
        self._require_same("駛出路口代號", self.exit_gate, exit_gate, line_no)
        self._require_same("車種代號", self.vehicle_class, vehicle_class, line_no)
        if time_s in self.times:
            raise ValueError(
                f"第 {line_no} 行的車輛 {self.vehicle_id!r} "
                f"在時間 {time_s} 秒重複出現"
            )
        self.times.add(time_s)
        self.sample_count += 1
        self.first_time_s = min(self.first_time_s, time_s)
        self.last_time_s = max(self.last_time_s, time_s)

    def _require_same(self, what, previous, current, line_no) -> None:
        if previous != current:
            raise ValueError(
                f"第 {line_no} 行的車輛 {self.vehicle_id!r} 的{what} "
                f"{current!r} 與第 {self.line_no} 行的 {previous!r} 不一致"
            )


def read_motc_ssam_vehicles(
    path: str | os.PathLike[str],
    *,
    encoding: str = "utf-8-sig",
) -> pd.DataFrame:
    """讀取 MOTC_SSAM 軌跡檔，回傳一列一台車的通過紀錄。

    座標本身不會留在結果裡，只用來確認每一列都是有效數值；需要逐時間步
    的位置時改用 :func:`read_motc_ssam_tracks`。

    Parameters
    ----------
    path : str or path-like
        MOTC_SSAM CSV 檔路徑。檔案開頭有 FORMAT／DIMENSIONS 區塊，
        本函式會略過它們，直到出現以 ``Timestep`` 開頭的表頭列。
    encoding : str, optional
        檔案編碼，預設 ``"utf-8-sig"``，有沒有 BOM 都讀得到。

    Returns
    -------
    pandas.DataFrame
        一列一台車，依 entry_time_s、vehicle_id 排序：

        =================  =========  ==================================
        欄位               型別       意義
        =================  =========  ==================================
        vehicle_id         string     車輛 ID
        entry_gate         string     進入路口代號，**已去掉結尾 I**
        exit_gate          string     駛出路口代號，**已去掉結尾 O**
        vehicle_class      string     車種代號
        entry_time_s       float64    該車最早出現的 Timestep
        exit_time_s        float64    該車最晚出現的 Timestep
        sample_count       int64      該車在檔案中的列數
        is_complete        bool       進出代號都不是 X
        is_crosswalk       bool       進入或駛出代號是行穿線代號
        =================  =========  ==================================

    Raises
    ------
    ValueError
        找不到表頭列、缺少必要欄位，或內容不符合格式（訊息會指出行號）。
    FileNotFoundError
        檔案不存在。

    Notes
    -----
    欄位刻意與 :func:`read_motc_su_vehicles` 對齊，可以直接餵給
    :func:`traffickit.volume.summarise_turn_volume`。**唯一的差別是
    SSAM 版沒有 frame 編號**，因此沒有 ``entry_frame`` 與 ``exit_frame``，
    改以 ``sample_count`` 表示該車的取樣列數。

    ``entry_time_s`` 與 ``exit_time_s`` 是檔案裡 ``Timestep`` 的原值，
    單位是秒。**它的時間原點由產製端決定，不保證與同一架次 Pixel Frame
    版的 frame 0 對齊**，兩版要合用時請自行校正。

    不完整軌跡（代號 X）與行穿線代號（例如 ``AB``）都會照樣讀入並分別
    標記 ``is_complete`` 與 ``is_crosswalk``，不會默默消失；需要時請自行
    ``.query("is_complete and not is_crosswalk")``。
    """
    vehicles = _collect_vehicles(path, encoding)
    rows = [
        (
            item.vehicle_id,
            item.entry_gate,
            item.exit_gate,
            item.vehicle_class,
            item.first_time_s,
            item.last_time_s,
            item.sample_count,
            item.is_complete,
            item.is_crosswalk,
        )
        for item in vehicles.values()
    ]
    frame = pd.DataFrame(rows, columns=list(_VEHICLE_DTYPES))
    frame = frame.astype(_VEHICLE_DTYPES)
    return frame.sort_values(
        ["entry_time_s", "vehicle_id"], kind="stable"
    ).reset_index(drop=True)


def read_motc_ssam_tracks(
    path: str | os.PathLike[str],
    *,
    encoding: str = "utf-8-sig",
) -> pd.DataFrame:
    """讀取 MOTC_SSAM 軌跡檔，回傳一列一台車一個時間步的位置。

    Parameters
    ----------
    path : str or path-like
        MOTC_SSAM CSV 檔路徑。
    encoding : str, optional
        檔案編碼，預設 ``"utf-8-sig"``。

    Returns
    -------
    pandas.DataFrame
        依 vehicle_id、time_s 排序。欄位為 vehicle_id、time_s、
        front_x_m／front_y_m（車頭中點）、rear_x_m／rear_y_m（車尾中點）、
        length_m／width_m（檔案宣告的車長與車寬）、
        x1_m…y4_m（還原出的四個角點）、
        center_x_m／center_y_m（四角點平均）、is_complete、is_crosswalk。
        最後兩欄是整台車的屬性，同一台車的每一列都相同。

    Raises
    ------
    ValueError
        找不到表頭列、缺少必要欄位，或內容不符合格式（訊息會指出行號）。
        車頭與車尾座標相同（無法決定車身方向）或車寬不是正數時也會拋錯。
    FileNotFoundError
        檔案不存在。

    Notes
    -----
    座標單位是**公尺**，直接取自檔案，不做任何換算。要畫到影像上才需要
    比例尺，那屬於呼叫端的事，本函式不提供比例尺參數。

    四個角點由車頭中點、車尾中點與車寬**幾何還原**，繞行順序與
    :func:`read_motc_su_tracks` 相同：x1／x2 是車頭兩角、x3／x4 是車尾兩角。
    這是把同一個車身矩形換一種參數表示，不是交通判定。
    **哪一角是「左」取決於座標系 Y 軸的方向**，而格式定義文件沒有寫明
    SSAM 的 Y 軸朝向，這一點尚未用真實資料確認。

    ``length_m`` 是檔案宣告的車長，**不等於車頭中點到車尾中點的距離**。
    實測一份真實檔，約 3% 的列兩者相差超過 0.5 公尺，最大差到 13.6 公尺
    （出現在聯結車車身）。還原角點時用的是車頭與車尾座標，不是這個欄位；
    要用哪一個取決於你要量的是什麼，本函式兩個都給。

    Speed 與 Acceleration 欄位**目前不讀**。實測顯示 Speed 的單位是公尺／秒
    （與相鄰時間步的位移比對，中位數比值 1.03），但這是量出來的、不是格式
    定義文件寫明的，因此先不納入契約。
    """
    columns, line_numbers = _collect_samples(path, encoding)
    if not line_numbers:
        return pd.DataFrame(
            {name: pd.Series(dtype=dtype) for name, dtype in _TRACK_DTYPES.items()}
        )

    frame = pd.DataFrame(columns)
    corners = _restore_corners(frame, line_numbers)
    for name, values in zip(_CORNER_COLUMNS, corners):
        frame[name] = values
    frame["center_x_m"] = (frame["front_x_m"] + frame["rear_x_m"]) / 2.0
    frame["center_y_m"] = (frame["front_y_m"] + frame["rear_y_m"]) / 2.0

    frame = frame.loc[:, list(_TRACK_DTYPES)].astype(_TRACK_DTYPES)
    return frame.sort_values(
        ["vehicle_id", "time_s"], kind="stable"
    ).reset_index(drop=True)


def _collect_vehicles(
    path: str | os.PathLike[str],
    encoding: str,
) -> dict[str, _Vehicle]:
    """讀完整份檔案，回傳每台車彙整後的紀錄。"""
    vehicles: dict[str, _Vehicle] = {}
    for line_no, values in _iter_rows(path, encoding):
        _index_vehicle(vehicles, values, line_no)
    return vehicles


def _collect_samples(
    path: str | os.PathLike[str],
    encoding: str,
) -> tuple[dict[str, list], list[int]]:
    """讀完整份檔案，回傳逐列的欄位與各列的行號。

    一致性檢查與 :func:`_collect_vehicles` 共用同一份 ``vehicles`` 索引，
    因此兩個入口讀同一份檔時，要嘛都成功、要嘛以相同理由失敗。
    """
    vehicles: dict[str, _Vehicle] = {}
    columns: dict[str, list] = {name: [] for name in (
        "vehicle_id", "time_s", *(name for name, _ in _NUMERIC_FIELDS),
        "is_complete", "is_crosswalk",
    )}
    line_numbers: list[int] = []

    for line_no, values in _iter_rows(path, encoding):
        vehicle = _index_vehicle(vehicles, values, line_no)
        columns["vehicle_id"].append(vehicle.vehicle_id)
        columns["time_s"].append(_parse_number(values["time_s"], line_no, "Timestep"))
        for name, header in _NUMERIC_FIELDS:
            columns[name].append(_parse_number(values[name], line_no, header))
        columns["is_complete"].append(vehicle.is_complete)
        columns["is_crosswalk"].append(vehicle.is_crosswalk)
        line_numbers.append(line_no)

    return columns, line_numbers


def _index_vehicle(
    vehicles: dict[str, _Vehicle],
    values: dict[str, str],
    line_no: int,
) -> _Vehicle:
    """把一列併進車輛索引，回傳該車的彙整紀錄。"""
    entry_gate, entry_kind = _motc_common.parse(values["entry_code"], "entry", line_no)
    exit_gate, exit_kind = _motc_common.parse(values["exit_code"], "exit", line_no)
    _motc_common.check_vehicle_class(values["vehicle_class"], line_no)
    time_s = _parse_number(values["time_s"], line_no, "Timestep")

    vehicle_id = values["vehicle_id"]
    if not vehicle_id:
        raise ValueError(f"第 {line_no} 行的車輛 ID 是空白")

    existing = vehicles.get(vehicle_id)
    if existing is None:
        existing = vehicles[vehicle_id] = _Vehicle(
            vehicle_id, entry_gate, exit_gate, entry_kind, exit_kind,
            values["vehicle_class"], time_s, line_no,
        )
    else:
        existing.add(entry_gate, exit_gate, values["vehicle_class"],
                     time_s, line_no)
    return existing


def _iter_rows(
    path: str | os.PathLike[str],
    encoding: str,
) -> Iterator[tuple[int, dict[str, str]]]:
    """逐列產生 ``(行號, {輸出欄位名: 原始字串})``，表頭之前的區塊略過。"""
    with open(path, "r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle)
        columns: dict[str, int] | None = None
        width = 0
        for row in reader:
            line_no = reader.line_num
            if columns is None:
                if row and row[0].strip().lower() == _HEADER_MARKER:
                    columns = _locate_columns(row, line_no)
                    width = max(columns.values()) + 1
                continue

            if not any(value.strip() for value in row):
                continue
            # SSAM 在每個時間步前插一列只有 Timestep 的分隔列。有些輸出會把
            # 後面的逗號補滿到與表頭同寬，所以判斷條件是「除了第一欄以外
            # 都是空的」，不能只看欄位數。
            if not any(value.strip() for value in row[1:]):
                continue
            if len(row) < width:
                raise ValueError(
                    f"第 {line_no} 行只有 {len(row)} 個欄位，"
                    f"必要欄位需要至少 {width} 個"
                )
            yield line_no, {
                name: row[index].strip() for name, index in columns.items()
            }

        if columns is None:
            raise ValueError(
                f"在 {os.fspath(path)} 找不到以 {_HEADER_MARKER!r} 開頭的表頭列"
            )


def _locate_columns(header: list[str], line_no: int) -> dict[str, int]:
    normalised = [value.strip().lower() for value in header]
    columns: dict[str, int] = {}
    missing: list[str] = []
    for name, wanted in (_TIME_FIELD, *_TEXT_FIELDS, *_NUMERIC_FIELDS):
        if wanted in normalised:
            columns[name] = normalised.index(wanted)
        else:
            missing.append(wanted)
    if missing:
        raise ValueError(
            f"第 {line_no} 行的表頭缺少必要欄位：{missing}；"
            f"實際欄位為 {[value.strip() for value in header]}"
        )
    return columns


def _parse_number(value: str, line_no: int, what: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise ValueError(
            f"第 {line_no} 行的 {what} {value!r} 不是數值"
        ) from None
    if not np.isfinite(number):
        raise ValueError(f"第 {line_no} 行的 {what} {value!r} 不是有限數值")
    return number


def _restore_corners(
    frame: pd.DataFrame,
    line_numbers: list[int],
) -> tuple[np.ndarray, ...]:
    """由車頭中點、車尾中點與車寬還原四個角點。

    角點順序對齊 Pixel Frame 版：先車頭兩角、再車尾兩角，繞行方向相同。
    """
    front_x = frame["front_x_m"].to_numpy()
    front_y = frame["front_y_m"].to_numpy()
    rear_x = frame["rear_x_m"].to_numpy()
    rear_y = frame["rear_y_m"].to_numpy()
    width = frame["width_m"].to_numpy()

    bad_width = width <= 0
    if bad_width.any():
        index = int(np.argmax(bad_width))
        raise ValueError(
            f"第 {line_numbers[index]} 行的車寬 {width[index]} 不是正數"
        )

    dx = front_x - rear_x
    dy = front_y - rear_y
    length = np.hypot(dx, dy)
    degenerate = length <= 0
    if degenerate.any():
        index = int(np.argmax(degenerate))
        raise ValueError(
            f"第 {line_numbers[index]} 行的車頭與車尾座標相同，無法決定車身方向"
        )

    # 車身方向的單位向量，與其垂直的單位向量（決定車寬往哪兩側展開）
    unit_x, unit_y = dx / length, dy / length
    perp_x, perp_y = unit_y, -unit_x
    half = width / 2.0

    return (
        front_x + perp_x * half, front_y + perp_y * half,
        front_x - perp_x * half, front_y - perp_y * half,
        rear_x - perp_x * half, rear_y - perp_y * half,
        rear_x + perp_x * half, rear_y + perp_y * half,
    )
