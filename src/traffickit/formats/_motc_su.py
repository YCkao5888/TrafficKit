"""MOTC_SU 空拍影像軌跡檔的讀取。

公開入口是 ``traffickit.formats`` 匯出的名稱；本檔案的其他名稱不保證穩定。

本模組屬於**格式轉換層**：只把檔案內容轉成套件契約的欄位與型別，
不做任何交通判定（不推轉向、不算速度、不裁時段、不排除任何車輛）。
"""

from __future__ import annotations

import os
import re
from typing import Iterator

import numpy as np
import pandas as pd

from .._validation import check_real

#: MOTC_SU 的車種代號。
#: h（聯結車車頭）與 g（聯結車車身）是**同一輛聯結車的兩列**，
#: 直接計數會把一輛車算成兩輛；統計時通常只保留 h。
MOTC_SU_VEHICLE_CLASSES: dict[str, str] = {
    "p": "行人",
    "u": "自行車",
    "m": "機車",
    "c": "汽車",
    "t": "貨車",
    "b": "巴士",
    "h": "聯結車車頭",
    "g": "聯結車車身",
}

#: 不完整軌跡的代號。官方定義為「請忽略」，本模組如實讀入並標記，
#: 由呼叫端決定要不要濾掉。
INCOMPLETE_CODE = "X"

#: 軌跡檔預設的影像張數／秒。實際拍攝速率是 9.99（29.97/3，NTSC 推導）；
#: 格式定義文件寫的是整數 10，兩者不同時以實際速率為準。
DEFAULT_FPS = 9.99

_FIELDS_BEFORE_TRACK = 6
_VALUES_PER_POINT = 8

_ENTRY_PATTERN = re.compile(r"^[A-Z]+I$")
_EXIT_PATTERN = re.compile(r"^[A-Z]+O$")

_VEHICLE_DTYPES = {
    "vehicle_id": "string",
    "entry_gate": "string",
    "exit_gate": "string",
    "vehicle_class": "string",
    "entry_frame": "int64",
    "exit_frame": "int64",
    "frame_count": "int64",
    "entry_time_s": "float64",
    "exit_time_s": "float64",
    "is_complete": "bool",
}

_POINT_COLUMNS = tuple(
    f"{axis}{index}_px" for index in range(1, 5) for axis in ("x", "y")
)

_TRACK_DTYPES = {
    "vehicle_id": "string",
    "frame": "int64",
    "time_s": "float64",
    **{name: "float64" for name in _POINT_COLUMNS},
    "center_x_px": "float64",
    "center_y_px": "float64",
    "is_complete": "bool",
}


class _Record:
    """一列剖析後的結果，只在本模組內流通。"""

    __slots__ = ("vehicle_id", "entry_code", "exit_code", "vehicle_class",
                 "entry_frame", "exit_frame", "tail", "line_no")

    def __init__(self, vehicle_id, entry_code, exit_code, vehicle_class,
                 entry_frame, exit_frame, tail, line_no):
        self.vehicle_id = vehicle_id
        self.entry_code = entry_code
        self.exit_code = exit_code
        self.vehicle_class = vehicle_class
        self.entry_frame = entry_frame
        self.exit_frame = exit_frame
        self.tail = tail
        self.line_no = line_no

    @property
    def frame_count(self) -> int:
        return self.exit_frame - self.entry_frame + 1

    @property
    def is_complete(self) -> bool:
        return (
            self.entry_code != INCOMPLETE_CODE
            and self.exit_code != INCOMPLETE_CODE
        )

    @property
    def entry_gate(self) -> str:
        return (
            self.entry_code
            if self.entry_code == INCOMPLETE_CODE
            else self.entry_code[:-1]
        )

    @property
    def exit_gate(self) -> str:
        return (
            self.exit_code
            if self.exit_code == INCOMPLETE_CODE
            else self.exit_code[:-1]
        )


def read_motc_su_vehicles(
    path: str | os.PathLike[str],
    *,
    fps: float = DEFAULT_FPS,
    encoding: str = "utf-8",
) -> pd.DataFrame:
    """讀取 MOTC_SU 軌跡檔，回傳一列一台車的通過紀錄。

    軌跡座標本身不會讀進記憶體，只驗證其數量；需要逐 frame 位置時改用
    :func:`read_motc_su_tracks`。

    Parameters
    ----------
    path : str or path-like
        MOTC_SU CSV 檔路徑。檔案沒有標題列。
    fps : float, optional
        影像張數／秒，用來把 frame 換算成秒。必須有限且大於 0。
        預設 9.99，也就是 29.97/3 的實際拍攝速率；格式定義文件寫的是整數
        10，兩者不同時以實際速率為準。拍攝設定不同時務必傳入正確值。
    encoding : str, optional
        檔案編碼，預設 "utf-8"。

    Returns
    -------
    pandas.DataFrame
        一列一台車，依 entry_frame、vehicle_id 排序：

        =================  =========  ==============================
        欄位               型別       意義
        =================  =========  ==============================
        vehicle_id         string     車輛 ID
        entry_gate         string     進入路口代號，**已去掉結尾 I**
        exit_gate          string     駛出路口代號，**已去掉結尾 O**
        vehicle_class      string     車種代號
        entry_frame        int64      進入路口的 frame
        exit_frame         int64      離開路口的 frame
        frame_count        int64      exit_frame - entry_frame + 1
        entry_time_s       float64    entry_frame / fps
        exit_time_s        float64    exit_frame / fps
        is_complete        bool       進出代號都不是 X
        =================  =========  ==============================

    Raises
    ------
    ValueError
        fps 無效，或檔案內容不符合格式（訊息會指出行號與原因）。
    FileNotFoundError
        檔案不存在。

    Notes
    -----
    **不完整軌跡（代號 X）會照樣讀入並標記 ``is_complete=False``**，
    不會默默消失。要餵給
    :func:`traffickit.volume.summarise_turn_volume` 前，請自行
    ``.query("is_complete")``——那個函式不接受 X 這種非路口代號。

    車種 ``h``（聯結車車頭）與 ``g``（聯結車車身）是同一輛車的兩列。
    做車輛數統計時通常只保留 ``h``；把 ``g`` 留在車種分組之外，
    它就會出現在 ``summary.unassigned_classes`` 而不會被默默計入。
    """
    seconds_per_frame = _frame_scale(fps)
    rows = []
    for record in _iter_records(path, encoding, validate_tail_length=True):
        rows.append((
            record.vehicle_id,
            record.entry_gate,
            record.exit_gate,
            record.vehicle_class,
            record.entry_frame,
            record.exit_frame,
            record.frame_count,
            record.entry_frame * seconds_per_frame,
            record.exit_frame * seconds_per_frame,
            record.is_complete,
        ))

    frame = pd.DataFrame(rows, columns=list(_VEHICLE_DTYPES))
    frame = frame.astype(_VEHICLE_DTYPES)
    _reject_duplicate_ids(frame)
    return frame.sort_values(
        ["entry_frame", "vehicle_id"], kind="stable"
    ).reset_index(drop=True)


def read_motc_su_tracks(
    path: str | os.PathLike[str],
    *,
    fps: float = DEFAULT_FPS,
    encoding: str = "utf-8",
) -> pd.DataFrame:
    """讀取 MOTC_SU 軌跡檔，回傳一列一台車一個 frame 的位置。

    Parameters
    ----------
    path : str or path-like
        MOTC_SU CSV 檔路徑。
    fps : float, optional
        影像張數／秒，預設 9.99。見 :func:`read_motc_su_vehicles`。
    encoding : str, optional
        檔案編碼，預設 "utf-8"。

    Returns
    -------
    pandas.DataFrame
        依 vehicle_id、frame 排序，欄位為 vehicle_id、frame、time_s、
        x1_px…y4_px（四個角點，第一點為車頭左上，順時針）、
        center_x_px、center_y_px（四角點平均）、is_complete。

    Raises
    ------
    ValueError
        fps 無效，或檔案內容不符合格式。
    FileNotFoundError
        檔案不存在。

    Notes
    -----
    座標單位是**像素**，原點在影像左上、Y 軸向下。要換算成公尺或計算速度，
    由呼叫端提供比例尺；本函式不做任何換算。

    一個 frame 一列，資料量約等於所有車輛的 frame 數總和，
    可能遠大於 :func:`read_motc_su_vehicles` 的結果。
    """
    seconds_per_frame = _frame_scale(fps)

    ids: list[str] = []
    frames: list[int] = []
    complete: list[bool] = []
    points: list[list[float]] = []
    for record in _iter_records(path, encoding, validate_tail_length=True):
        values = _parse_tail(record)
        count = record.frame_count
        ids.extend([record.vehicle_id] * count)
        frames.extend(range(record.entry_frame, record.exit_frame + 1))
        complete.extend([record.is_complete] * count)
        points.append(values)

    if not ids:
        return pd.DataFrame(
            {name: pd.Series(dtype=dtype)
             for name, dtype in _TRACK_DTYPES.items()}
        )

    coordinates = np.concatenate(points).reshape(-1, _VALUES_PER_POINT)
    frame = pd.DataFrame(coordinates, columns=list(_POINT_COLUMNS))
    frame.insert(0, "vehicle_id", ids)
    frame.insert(1, "frame", frames)
    frame.insert(2, "time_s", np.asarray(frames) * seconds_per_frame)
    frame["center_x_px"] = coordinates[:, 0::2].mean(axis=1)
    frame["center_y_px"] = coordinates[:, 1::2].mean(axis=1)
    frame["is_complete"] = complete

    frame = frame.loc[:, list(_TRACK_DTYPES)].astype(_TRACK_DTYPES)
    return frame.sort_values(
        ["vehicle_id", "frame"], kind="stable"
    ).reset_index(drop=True)


def _frame_scale(fps: float) -> float:
    return 1.0 / check_real("fps", fps, minimum=0.0, allow_minimum=False)


def _iter_records(
    path: str | os.PathLike[str],
    encoding: str,
    *,
    validate_tail_length: bool,
) -> Iterator[_Record]:
    with open(path, "r", encoding=encoding, newline="") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            yield _parse_line(line, line_no, validate_tail_length)


def _parse_line(line: str, line_no: int, validate_tail_length: bool) -> _Record:
    head = line.split(",", _FIELDS_BEFORE_TRACK)
    if len(head) < _FIELDS_BEFORE_TRACK:
        raise ValueError(
            f"第 {line_no} 行只有 {len(head)} 個欄位，"
            f"至少需要 {_FIELDS_BEFORE_TRACK} 個"
        )
    vehicle_id, entry_raw, exit_raw, entry_code, exit_code, vehicle_class = (
        value.strip() for value in head[:_FIELDS_BEFORE_TRACK]
    )
    tail = head[_FIELDS_BEFORE_TRACK] if len(head) > _FIELDS_BEFORE_TRACK else ""

    if not vehicle_id:
        raise ValueError(f"第 {line_no} 行的車輛 ID 是空白")
    entry_frame = _parse_frame(entry_raw, line_no, "進入路口 frame")
    exit_frame = _parse_frame(exit_raw, line_no, "離開路口 frame")
    if exit_frame < entry_frame:
        raise ValueError(
            f"第 {line_no} 行的離開 frame（{exit_frame}）"
            f"早於進入 frame（{entry_frame}）"
        )

    _check_gate_code(entry_code, _ENTRY_PATTERN, "進入", line_no)
    _check_gate_code(exit_code, _EXIT_PATTERN, "離開", line_no)
    if vehicle_class not in MOTC_SU_VEHICLE_CLASSES:
        raise ValueError(
            f"第 {line_no} 行的車種代號 {vehicle_class!r} 不在格式定義內："
            f"{sorted(MOTC_SU_VEHICLE_CLASSES)}"
        )

    record = _Record(
        vehicle_id, entry_code, exit_code, vehicle_class,
        entry_frame, exit_frame, tail, line_no,
    )
    if validate_tail_length:
        # 不變式：軌跡值數量 = 8 × frame 數。用來擋住錯位或截斷的檔案。
        actual = tail.count(",") + 1 if tail else 0
        expected = _VALUES_PER_POINT * record.frame_count
        if actual != expected:
            raise ValueError(
                f"第 {line_no} 行有 {actual} 個軌跡值，"
                f"但 frame 數 {record.frame_count} 應對應 {expected} 個"
            )
    return record


def _parse_frame(value: str, line_no: int, what: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise ValueError(
            f"第 {line_no} 行的{what} {value!r} 不是整數"
        ) from None
    if number < 0:
        raise ValueError(f"第 {line_no} 行的{what} {number} 是負數")
    return number


def _check_gate_code(
    code: str,
    pattern: re.Pattern[str],
    what: str,
    line_no: int,
) -> None:
    if code == INCOMPLETE_CODE or pattern.match(code):
        return
    raise ValueError(
        f"第 {line_no} 行的{what}路口代號 {code!r} 不符合格式："
        f"應為 {pattern.pattern} 或 {INCOMPLETE_CODE!r}"
    )


def _parse_tail(record: _Record) -> np.ndarray:
    try:
        return np.array(record.tail.split(","), dtype="float64")
    except ValueError:
        raise ValueError(
            f"第 {record.line_no} 行的軌跡座標含有非數值"
        ) from None


def _reject_duplicate_ids(frame: pd.DataFrame) -> None:
    duplicated = frame.loc[frame.duplicated("vehicle_id"), "vehicle_id"]
    if not duplicated.empty:
        sample = sorted(set(duplicated))[:5]
        raise ValueError(
            f"檔案中的車輛 ID 重複：{sample}"
            + ("…" if len(set(duplicated)) > 5 else "")
        )
