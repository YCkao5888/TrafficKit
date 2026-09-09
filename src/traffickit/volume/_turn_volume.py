"""轉向流量統計的內部實作。

公開入口是 ``traffickit.volume.summarise_turn_volume``；
本檔案的其他名稱不保證穩定。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd
from pandas.api.types import is_bool_dtype

from .._validation import (
    check_label_column,
    check_real,
    check_unique,
    require_columns,
    require_dataframe,
)

#: 本套件承認的轉向類別，同時也是輸出的排序順序。
TURNS = ("left", "straight", "right", "u_turn")

#: 舊版轉向流量調查 UI 的預設車種分組（車種代碼取自既有專案設定）。
#: **必須明確傳入**，不是函式預設值；不同案件的車種對照可能不同。
DEFAULT_VEHICLE_GROUPS: Mapping[str, tuple[str, ...]] = {
    "大型車": ("b", "t", "h"),
    "小型車": ("c",),
    "機車": ("m",),
}

#: 舊版轉向流量調查 UI 的預設 PCU 權重。
#: 來源是既有程式的設定值，本套件不認定它等同任何法規或手冊的規定值；
#: 實際採用哪一組權重由呼叫端決定並記錄。
DEFAULT_PCU_WEIGHTS: Mapping[str, Mapping[str, float]] = {
    "大型車": {"left": 2.0, "straight": 1.8, "right": 2.7, "u_turn": 2.0},
    "小型車": {"left": 1.05, "straight": 1.0, "right": 1.08, "u_turn": 1.05},
    "機車": {"left": 0.43, "straight": 0.42, "right": 0.45, "u_turn": 0.43},
}

_REQUIRED_PASSAGES = ("vehicle_id", "entry_gate", "exit_gate", "vehicle_class")
_REQUIRED_MOVEMENTS = ("entry_gate", "exit_gate", "turn", "is_allowed")

_MOVEMENT_DTYPES = {
    "entry_gate": "string",
    "exit_gate": "string",
    "turn": "string",
    "vehicle_group": "string",
    "is_allowed": "bool",
    "vehicle_count": "int64",
    "pcu_weight": "float64",
    "pcu": "float64",
}

_BY_TURN_DTYPES = {
    key: value
    for key, value in _MOVEMENT_DTYPES.items()
    if key != "exit_gate"
}


@dataclass(frozen=True)
class TurnVolumeSummary:
    """轉向流量統計的分母與例外計數。

    ``input_vehicle_count == counted_vehicle_count + unassigned_vehicle_count``。
    """

    input_vehicle_count: int
    counted_vehicle_count: int
    total_pcu: float
    unassigned_vehicle_count: int
    unassigned_classes: tuple[str, ...]
    disallowed_vehicle_count: int


@dataclass(frozen=True)
class TurnVolume:
    """轉向流量統計結果。

    Attributes
    ----------
    movements : pandas.DataFrame
        最細粒度，一列 = 進入閘門 × 駛出閘門 × 轉向 × 車種分組：
        entry_gate、exit_gate、turn、vehicle_group、is_allowed、
        vehicle_count、pcu_weight、pcu。
        **``movements`` 參數定義的每一個轉向都會出現**，沒有車就是 0，
        因此呼叫端可以區分「合法但 0 台」與「這個方向不允許轉」。
    by_turn : pandas.DataFrame
        報表用，一列 = 進入閘門 × 轉向 × 車種分組（把駛出閘門加總）。
        同一 (entry_gate, turn) 只要**有任一**駛出閘門允許，
        ``is_allowed`` 即為 True。
    summary : TurnVolumeSummary
        總計與各項分母。
    vehicle_groups : tuple of str
        本次採用的分組名稱，順序與傳入的 ``vehicle_groups`` 相同，
        可直接拿來產生報表欄位。
    turns : tuple of str
        本次 ``movements`` 中出現的轉向，依 :data:`TURNS` 順序排列。
    """

    movements: pd.DataFrame
    by_turn: pd.DataFrame
    summary: TurnVolumeSummary
    vehicle_groups: tuple[str, ...]
    turns: tuple[str, ...]


def summarise_turn_volume(
    passages: pd.DataFrame,
    *,
    movements: pd.DataFrame,
    vehicle_groups: Mapping[str, Iterable[str]],
    pcu_weights: Mapping[str, Mapping[str, float]],
) -> TurnVolume:
    """統計各進入方向、各轉向、各車種分組的車輛數與 PCU。

    轉向類別不由本函式推斷，而是查 ``movements`` 對照表得到；因此本函式
    也知道哪些轉向合法，能把「合法但沒有車」與「這個方向不允許轉」分開。

    Parameters
    ----------
    passages : pandas.DataFrame
        一列一台車的通過紀錄。必要欄位：vehicle_id（非空白字串、不可重複）、
        entry_gate、exit_gate、vehicle_class（皆為非空白字串）。
        允許未排序或含額外欄位；不修改輸入。
        同一台車若在資料範圍內通過兩次，呼叫端須給不同的 vehicle_id。
    movements : pandas.DataFrame
        路口的轉向定義。必要欄位：entry_gate、exit_gate、turn、is_allowed。
        turn 必須是 ``left`` / ``straight`` / ``right`` / ``u_turn`` 之一；
        is_allowed 必須是布林欄位；(entry_gate, exit_gate) 不可重複；
        至少一列。
    vehicle_groups : mapping of str to iterable of str
        分組名稱 → 車種代碼。同一車種不可出現在兩個分組。
        分組順序即輸出與報表的欄位順序。
    pcu_weights : mapping of str to mapping of str to float
        分組名稱 → {轉向: PCU 權重}。每個分組都要涵蓋 ``movements`` 中
        出現的每一個轉向；權重須為有限、非負的實數。
        不提供預設權重，避免呼叫端忘記設定時套用來源不明的數字；
        需要舊版 UI 的預設值時，明確傳入 :data:`DEFAULT_PCU_WEIGHTS`。

    Returns
    -------
    TurnVolume
        最細粒度表、報表彙整表與分母統計。

    Raises
    ------
    TypeError
        passages 或 movements 不是 DataFrame。
    ValueError
        欄位、數值、參數不符合規格，或資料中出現 ``movements``
        未定義的 (entry_gate, exit_gate) 組合。

    Notes
    -----
    本函式不判定閘門進出、不切時段、不算百分比，也不讀寫檔案。
    軌跡到進出閘門的判定、分析時段的裁切由呼叫端先完成；
    百分比與小計是版面呈現，用 ``movements`` 或 ``by_turn`` 自行 groupby 即可。

    車種未被任何分組涵蓋的車輛**不計入統計**，但會記錄在
    ``summary.unassigned_vehicle_count`` 與 ``summary.unassigned_classes``。

    ``is_allowed`` 為 False 的轉向若出現車輛，仍會照實計數（可視為違規轉向），
    並記錄在 ``summary.disallowed_vehicle_count``。
    """
    require_dataframe(passages, "passages")
    require_dataframe(movements, "movements")

    group_order, class_to_group = _validated_groups(vehicle_groups)
    turn_table = _validated_movements(movements)
    used_turns = tuple(
        turn for turn in TURNS if turn in set(turn_table["turn"])
    )
    weight_table = _validated_weights(pcu_weights, group_order, used_turns)

    work = _validated_passages(passages)
    work["vehicle_group"] = work["vehicle_class"].map(class_to_group)

    _reject_undefined_movements(work, turn_table)

    unassigned = work.loc[work["vehicle_group"].isna()]
    counted = work.loc[work["vehicle_group"].notna()]

    detail = _build_movement_grid(
        counted, turn_table, group_order, weight_table
    )
    by_turn = _aggregate_by_turn(detail, group_order)

    return TurnVolume(
        movements=detail,
        by_turn=by_turn,
        summary=TurnVolumeSummary(
            input_vehicle_count=int(len(work)),
            counted_vehicle_count=int(len(counted)),
            total_pcu=float(detail["pcu"].sum()),
            unassigned_vehicle_count=int(len(unassigned)),
            unassigned_classes=tuple(
                sorted(set(unassigned["vehicle_class"]))
            ),
            disallowed_vehicle_count=int(
                detail.loc[~detail["is_allowed"], "vehicle_count"].sum()
            ),
        ),
        vehicle_groups=tuple(group_order),
        turns=used_turns,
    )


def _validated_groups(
    vehicle_groups: Mapping[str, Iterable[str]],
) -> tuple[list[str], dict[str, str]]:
    if not isinstance(vehicle_groups, Mapping):
        raise ValueError("vehicle_groups 必須是「分組名稱 → 車種代碼」的對照")
    if not vehicle_groups:
        raise ValueError("vehicle_groups 至少需要一個分組")

    order: list[str] = []
    class_to_group: dict[str, str] = {}
    for name, classes in vehicle_groups.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("vehicle_groups 的分組名稱必須是非空白字串")
        if isinstance(classes, (str, bytes)) or not isinstance(
            classes, Iterable
        ):
            raise ValueError(f"vehicle_groups[{name!r}] 必須是車種代碼的序列")
        members = list(classes)
        if not members:
            raise ValueError(f"vehicle_groups[{name!r}] 至少需要一個車種")
        for code in members:
            if not isinstance(code, str) or not code.strip():
                raise ValueError(
                    f"vehicle_groups[{name!r}] 的車種代碼必須是非空白字串"
                )
            if code in class_to_group:
                raise ValueError(
                    f"車種 {code!r} 同時出現在 {class_to_group[code]!r} 與 "
                    f"{name!r}；同一車種只能屬於一個分組"
                )
            class_to_group[code] = name
        order.append(name)
    return order, class_to_group


def _validated_movements(movements: pd.DataFrame) -> pd.DataFrame:
    require_columns(movements, _REQUIRED_MOVEMENTS, name="movements")
    table = movements.loc[:, list(_REQUIRED_MOVEMENTS)].copy()
    if table.empty:
        raise ValueError("movements 至少需要一列轉向定義")

    for column in ("entry_gate", "exit_gate", "turn"):
        check_label_column(table, column)
    unknown = sorted(set(table["turn"]) - set(TURNS))
    if unknown:
        raise ValueError(f"movements 的 turn 只接受 {list(TURNS)}，收到：{unknown}")
    if not is_bool_dtype(table["is_allowed"].dtype):
        raise ValueError("movements 的 is_allowed 必須是布林欄位")
    check_unique(
        table,
        ["entry_gate", "exit_gate"],
        message="movements 的 (entry_gate, exit_gate) 不可重複",
    )

    for column in ("entry_gate", "exit_gate", "turn"):
        table[column] = table[column].astype("string")
    table["is_allowed"] = table["is_allowed"].astype("bool")
    return table.reset_index(drop=True)


def _validated_weights(
    pcu_weights: Mapping[str, Mapping[str, float]],
    group_order: list[str],
    used_turns: tuple[str, ...],
) -> pd.DataFrame:
    if not isinstance(pcu_weights, Mapping):
        raise ValueError("pcu_weights 必須是「分組名稱 → {轉向: 權重}」的對照")

    rows = []
    for group in group_order:
        weights = pcu_weights.get(group)
        if not isinstance(weights, Mapping):
            raise ValueError(f"pcu_weights 缺少分組 {group!r} 的權重")
        for turn in used_turns:
            if turn not in weights:
                raise ValueError(
                    f"pcu_weights[{group!r}] 缺少轉向 {turn!r} 的權重"
                )
            rows.append({
                "vehicle_group": group,
                "turn": turn,
                "pcu_weight": check_real(
                    f"pcu_weights[{group!r}][{turn!r}]",
                    weights[turn],
                    minimum=0.0,
                ),
            })
    return pd.DataFrame(rows)


def _validated_passages(passages: pd.DataFrame) -> pd.DataFrame:
    require_columns(passages, _REQUIRED_PASSAGES, name="passages")

    # 複製必要欄位，避免修改呼叫端持有的原始資料。
    work = passages.loc[:, list(_REQUIRED_PASSAGES)].copy()
    if work.empty:
        for column in _REQUIRED_PASSAGES:
            work[column] = work[column].astype("string")
        return work.reset_index(drop=True)

    for column in _REQUIRED_PASSAGES:
        check_label_column(work, column)
    check_unique(
        work,
        ["vehicle_id"],
        message=(
            "passages 的 vehicle_id 不可重複；一列代表一台車的一次通過，"
            "同一台車通過兩次請給不同的 vehicle_id"
        ),
    )
    for column in _REQUIRED_PASSAGES:
        work[column] = work[column].astype("string")
    return work.reset_index(drop=True)


def _reject_undefined_movements(
    work: pd.DataFrame,
    turn_table: pd.DataFrame,
) -> None:
    if work.empty:
        return
    defined = set(zip(turn_table["entry_gate"], turn_table["exit_gate"]))
    seen = set(zip(work["entry_gate"], work["exit_gate"]))
    undefined = sorted(seen - defined)
    if undefined:
        raise ValueError(
            "passages 出現 movements 未定義的 (entry_gate, exit_gate)："
            f"{undefined[:5]}"
            + ("…" if len(undefined) > 5 else "")
        )


def _build_movement_grid(
    counted: pd.DataFrame,
    turn_table: pd.DataFrame,
    group_order: list[str],
    weight_table: pd.DataFrame,
) -> pd.DataFrame:
    groups = pd.DataFrame({
        "vehicle_group": pd.Series(group_order, dtype="string"),
        # 分組順序即報表欄位順序，排序時用得到。
        "_group_rank": range(len(group_order)),
    })
    grid = turn_table.merge(groups, how="cross")

    counts = (
        counted.groupby(
            ["entry_gate", "exit_gate", "vehicle_group"], sort=False
        )
        .size()
        .reset_index(name="vehicle_count")
    )
    grid = grid.merge(
        counts, on=["entry_gate", "exit_gate", "vehicle_group"], how="left"
    )
    grid["vehicle_count"] = grid["vehicle_count"].fillna(0).astype("int64")

    grid = grid.merge(weight_table, on=["vehicle_group", "turn"], how="left")
    grid["pcu"] = grid["vehicle_count"] * grid["pcu_weight"]

    return _sorted_output(grid, _MOVEMENT_DTYPES, ["exit_gate", "_group_rank"])


def _aggregate_by_turn(
    detail: pd.DataFrame,
    group_order: list[str],
) -> pd.DataFrame:
    ranks = {name: index for index, name in enumerate(group_order)}
    grouped = (
        detail.groupby(["entry_gate", "turn", "vehicle_group"], sort=False)
        .agg(
            # 同一 (entry_gate, turn) 只要有任一駛出閘門允許就算允許，
            # 與舊版報表 allowed_turns 的判定一致。
            is_allowed=("is_allowed", "any"),
            vehicle_count=("vehicle_count", "sum"),
            pcu_weight=("pcu_weight", "first"),
            pcu=("pcu", "sum"),
        )
        .reset_index()
    )
    grouped["_group_rank"] = grouped["vehicle_group"].map(ranks)
    return _sorted_output(grouped, _BY_TURN_DTYPES, ["_group_rank"])


def _sorted_output(
    frame: pd.DataFrame,
    dtypes: Mapping[str, str],
    tie_breakers: list[str],
) -> pd.DataFrame:
    ranks = {turn: index for index, turn in enumerate(TURNS)}
    frame = frame.copy()
    frame["_turn_rank"] = frame["turn"].map(ranks)
    frame = frame.sort_values(
        ["entry_gate", "_turn_rank"] + tie_breakers, kind="stable"
    )
    result = frame.loc[:, list(dtypes)].astype(dict(dtypes))
    return result.reset_index(drop=True)
