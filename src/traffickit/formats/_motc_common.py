"""MOTC 空拍影像軌跡格式的共用定義。

Pixel Frame 版（MOTC_SU）與 SSAM 版出自同一份客戶端格式定義文件
（本機參考，未納入版控），共用同一套**車種代號**與**路口代號**約定，
因此這些定義放在這裡，由兩個讀取器共同引用。

路口代號的約定：

- 路口代號順時針編號，從左側路口起為 A，依序 B、C、D。
- 進入路口的代號結尾是 ``I``、離開是 ``O``（例如 ``AI``、``CO``）。
- ``X`` 代表不完整軌跡。
- **行人走行穿線，代號是兩個路口字母**，例如 ``AB``、``BC``，
  沒有 I／O 後綴，也不對應任何單一進出方向。

本模組只認代號的**字面格式**，不知道現場有幾個分支、也不驗證代號是否
真的存在於該路口；那是呼叫端提供 ``movements`` 對照表時的責任。
"""

from __future__ import annotations

#: MOTC 空拍影像軌跡檔的車種代號。**Pixel Frame 版與 SSAM 版完全相同**
#: （格式定義文件的兩個分頁列出同一份清單）。
#: h（聯結車車頭）與 g（聯結車車身）是**同一輛聯結車的兩列**，
#: 直接計數會把一輛車算成兩輛；統計時通常只保留 h。
#:
#: 名稱保留 ``MOTC_SU_`` 前綴是為了不破壞既有呼叫端，內容並不限於 SU 版。
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

#: 不完整軌跡的代號。格式定義文件說「請忽略」，本套件如實讀入並標記，
#: 由呼叫端決定要不要濾掉。
INCOMPLETE_CODE = "X"

#: 一般進出代號（去掉 I／O 後綴後就是路口代號）。
GATE = "gate"
#: 行穿線代號，兩個路口字母，例如 ``AB``。
CROSSWALK = "crosswalk"
#: 不完整軌跡代號 ``X``。
INCOMPLETE = "incomplete"

_SUFFIXES = {"entry": "I", "exit": "O"}
_LABELS = {"entry": "進入", "exit": "離開"}

# I 與 O 是後綴字母，不能同時當成行穿線代號的第二個字母，否則 'AI' 會被
# 誤判成「A 路口到 I 路口的行穿線」。分支數在 8 以內時字母排到 H 為止，
# 不會用到 I／O，所以這個排除不會誤傷真實資料。
_SUFFIX_LETTERS = frozenset("IO")


def classify(code: str, direction: str) -> str:
    """判斷代號屬於哪一類，不符合任何一類時回傳空字串。

    Parameters
    ----------
    code : str
        原始代號，例如 ``"AI"``、``"AB"``、``"X"``。
    direction : {"entry", "exit"}
        這個代號出現在進入欄還是離開欄。決定後綴要找 ``I`` 還是 ``O``。

    Returns
    -------
    str
        :data:`GATE`、:data:`CROSSWALK`、:data:`INCOMPLETE` 其中之一；
        格式不符時回傳 ``""``。
    """
    if code == INCOMPLETE_CODE:
        return INCOMPLETE

    suffix = _SUFFIXES[direction]
    if len(code) >= 2 and code.endswith(suffix) and _is_gate_letters(code[:-1]):
        return GATE

    if len(code) == 2 and _is_gate_letters(code) and code[-1] not in _SUFFIX_LETTERS:
        return CROSSWALK

    return ""


def label(code: str, kind: str) -> str:
    """回傳要寫進輸出表的代號：一般代號去掉 I／O 後綴，其餘原樣保留。"""
    return code[:-1] if kind == GATE else code


def parse(code: str, direction: str, line_no: int) -> tuple[str, str]:
    """剖析一個代號，回傳 ``(輸出用代號, 類別)``；格式不符則拋 ``ValueError``。"""
    kind = classify(code, direction)
    if not kind:
        suffix = _SUFFIXES[direction]
        raise ValueError(
            f"第 {line_no} 行的{_LABELS[direction]}路口代號 {code!r} 不符合格式："
            f"應為路口代號加結尾 {suffix!r}（例如 {'A' + suffix!r}）、"
            f"行穿線代號（兩個路口字母，例如 'AB'）"
            f"或 {INCOMPLETE_CODE!r}"
        )
    return label(code, kind), kind


def check_vehicle_class(code: str, line_no: int) -> str:
    """確認車種代號在格式定義內，並原樣回傳；不在則拋 ``ValueError``。"""
    if code not in MOTC_SU_VEHICLE_CLASSES:
        raise ValueError(
            f"第 {line_no} 行的車種代號 {code!r} 不在格式定義內："
            f"{sorted(MOTC_SU_VEHICLE_CLASSES)}"
        )
    return code


def _is_gate_letters(text: str) -> bool:
    return bool(text) and text.isascii() and text.isalpha() and text.isupper()
