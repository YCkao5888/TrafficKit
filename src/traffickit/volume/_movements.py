"""由順時針路口代號推導轉向對照表。

公開入口是 ``traffickit.volume.clockwise_movements``；
本檔案的其他名稱不保證穩定。
"""

from __future__ import annotations

from typing import Iterable, Sequence

import pandas as pd

_MOVEMENT_DTYPES = {
    "entry_gate": "string",
    "exit_gate": "string",
    "turn": "string",
    "is_allowed": "bool",
}


def clockwise_movements(
    gates: Sequence[str],
    *,
    disallowed: Iterable[tuple[str, str]] = (),
) -> pd.DataFrame:
    """依順時針排列的路口代號，產生完整的轉向對照表。

    適用於路口分支**依順時針命名**的資料（例如 MOTC_SU 軌跡檔的
    A、B、C、D：順時針從左側路口起算）。此時轉向類別可由幾何推導：
    車輛由第 i 個分支駛入時，順時針方向的下一個分支就在它的左手邊。

    設 ``offset = (j - i) mod n``：

    ========  ==========
    offset    轉向
    ========  ==========
    0         u_turn
    < n / 2   left
    n / 2     straight
    > n / 2   right
    ========  ==========

    Parameters
    ----------
    gates : sequence of str
        **依順時針排列**的路口代號，非空白且不重複，數量必須是**偶數**
        且至少 2 個。奇數分支（例如五岔路口）沒有正對面的分支，
        「直行」無法只靠編號判斷，請自行撰寫對照表。
    disallowed : iterable of (str, str), optional
        不允許的 (進入, 駛出) 組合，這些列的 ``is_allowed`` 為 False。
        兩個代號都必須出現在 ``gates`` 內。

    Returns
    -------
    pandas.DataFrame
        ``n × n`` 列，欄位 entry_gate、exit_gate、turn、is_allowed，
        可直接當作 :func:`summarise_turn_volume` 的 ``movements``。
        依 ``gates`` 的順序排列。

    Raises
    ------
    ValueError
        代號空白、重複、數量不是偶數，或 ``disallowed`` 含未知代號。

    Notes
    -----
    **本函式只推導轉向的幾何類別，不知道現場的管制規定。**
    產生的表格預設每一個組合都 ``is_allowed=True``，這在多數路口是錯的
    ——尤其是迴轉。請務必依現場標誌標線把不允許的組合填進 ``disallowed``，
    否則違規轉向會被當成合法轉向統計。

    分支若沒有等角度分布（例如歪斜路口、Y 型路口），編號推導出的
    「直行／左轉／右轉」可能與現場認知不同，此時同樣應自行撰寫對照表。
    """
    names = _validated_gates(gates)
    count = len(names)
    blocked = _validated_disallowed(disallowed, names)

    rows = []
    for entry_index, entry_gate in enumerate(names):
        for exit_index, exit_gate in enumerate(names):
            offset = (exit_index - entry_index) % count
            rows.append((
                entry_gate,
                exit_gate,
                _turn_for_offset(offset, count),
                (entry_gate, exit_gate) not in blocked,
            ))
    return pd.DataFrame(
        rows, columns=list(_MOVEMENT_DTYPES)
    ).astype(_MOVEMENT_DTYPES)


def _turn_for_offset(offset: int, count: int) -> str:
    if offset == 0:
        return "u_turn"
    half = count // 2
    if offset == half:
        return "straight"
    return "left" if offset < half else "right"


def _validated_gates(gates: Sequence[str]) -> list[str]:
    if isinstance(gates, (str, bytes)) or not isinstance(gates, Iterable):
        raise ValueError("gates 必須是路口代號的序列")
    names = list(gates)
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("gates 的路口代號必須是非空白字串")
    if len(set(names)) != len(names):
        raise ValueError("gates 的路口代號不可重複")
    if len(names) < 2:
        raise ValueError("gates 至少需要兩個路口代號")
    if len(names) % 2:
        raise ValueError(
            f"gates 有 {len(names)} 個分支；奇數分支沒有正對面的分支，"
            "無法只靠順時針編號判斷直行，請自行撰寫 movements 對照表"
        )
    return names


def _validated_disallowed(
    disallowed: Iterable[tuple[str, str]],
    names: list[str],
) -> set[tuple[str, str]]:
    if isinstance(disallowed, (str, bytes)) or not isinstance(
        disallowed, Iterable
    ):
        raise ValueError("disallowed 必須是 (進入, 駛出) 組合的序列")
    known = set(names)
    blocked = set()
    for item in disallowed:
        if isinstance(item, (str, bytes)) or not isinstance(item, Iterable):
            raise ValueError("disallowed 的每一項必須是 (進入, 駛出) 組合")
        pair = tuple(item)
        if len(pair) != 2:
            raise ValueError("disallowed 的每一項必須剛好兩個代號")
        unknown = [name for name in pair if name not in known]
        if unknown:
            raise ValueError(f"disallowed 出現不在 gates 內的代號：{unknown}")
        blocked.add((pair[0], pair[1]))
    return blocked
