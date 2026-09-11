"""顏色剖析與配色。

OpenCV 的通道順序是 **BGR**，本模組一律以 BGR 三元組流通，只在與人互動的
介面（十六進位字串、顏色名稱）邊界做轉換。
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

#: 預設配色（BGR），依指定順序輪流指派。
DEFAULT_PALETTE: tuple[tuple[int, int, int], ...] = (
    (0, 0, 255),      # 紅
    (0, 255, 0),      # 綠
    (255, 128, 0),    # 藍
    (0, 255, 255),    # 黃
    (255, 0, 255),    # 洋紅
    (255, 255, 0),    # 青
    (0, 165, 255),    # 橘
    (128, 0, 255),    # 粉
    (0, 215, 255),    # 金
    (128, 255, 0),    # 春綠
)

#: 可以用名稱指定的顏色（BGR）。
NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "red": (0, 0, 255), "green": (0, 255, 0), "blue": (255, 0, 0),
    "yellow": (0, 255, 255), "cyan": (255, 255, 0), "magenta": (255, 0, 255),
    "orange": (0, 165, 255), "pink": (203, 192, 255), "purple": (128, 0, 128),
    "white": (255, 255, 255), "black": (0, 0, 0), "gray": (128, 128, 128),
    "grey": (128, 128, 128),
}


def parse_color(spec: str | Sequence[int]) -> tuple[int, int, int]:
    """把顏色寫法轉成 BGR 三元組。

    Parameters
    ----------
    spec : str or sequence of int
        接受四種寫法：顏色名稱（``"red"``）、十六進位（``"#FF0000"``）、
        逗號分隔的 RGB 字串（``"255,0,0"``），或已經是 BGR 的三元組。
        字串的名稱與十六進位不分大小寫。

    Returns
    -------
    tuple of int
        ``(B, G, R)``，每個分量介於 0 與 255 之間。

    Raises
    ------
    TypeError
        spec 既不是字串也不是三個元素的序列。
    ValueError
        字串無法解析，或數值超出 0–255。

    Notes
    -----
    **字串寫法一律是 RGB 順序，回傳值一律是 BGR 順序。** 這個不對稱是刻意的：
    ``#FF0000`` 對人來說就是紅色，而 OpenCV 要的是 ``(0, 0, 255)``。
    轉換只在這裡發生，套件內部不再出現 RGB。

    超出範圍的數值**拋錯而不是夾到邊界**。夾邊界會把打錯的值默默變成一個
    看起來正常的顏色。
    """
    if isinstance(spec, str):
        return _parse_color_string(spec)

    if isinstance(spec, (bytes, bytearray)) or not isinstance(spec, Iterable):
        raise TypeError(
            f"顏色必須是字串或三個整數的序列，收到 {type(spec).__name__}"
        )

    values = list(spec)
    if len(values) != 3:
        raise ValueError(f"顏色序列必須剛好三個分量，收到 {len(values)} 個")
    return tuple(_check_channel(value, spec) for value in values)


def color_to_hex(color: Sequence[int]) -> str:
    """BGR 三元組 → ``"#RRGGBB"``，給介面上的色塊與訊息用。"""
    blue, green, red = (_check_channel(value, color) for value in color)
    return f"#{red:02x}{green:02x}{blue:02x}"


def assign_colors(
    vehicle_ids: Sequence[str],
    *,
    palette: Sequence[Sequence[int]] = DEFAULT_PALETTE,
    overrides: Mapping[str, str | Sequence[int]] | None = None,
) -> dict[str, tuple[int, int, int]]:
    """替一批車輛配色，回傳 ``{車輛 ID: BGR}``。

    Parameters
    ----------
    vehicle_ids : sequence of str
        要配色的車輛 ID，**順序即配色順序**。重複的只算第一次。
    palette : sequence, optional
        自動配色用的色票，依序輪流指派。預設 :data:`DEFAULT_PALETTE`。
    overrides : mapping, optional
        指定某幾台車的顏色，寫法同 :func:`parse_color`。
        被指定的車輛**仍然佔用一個配色順位**，這樣增減指定不會讓其他車
        的顏色跟著跳動。

    Returns
    -------
    dict
        每個車輛 ID 對應一個 BGR 三元組。

    Raises
    ------
    ValueError
        palette 是空的，或 overrides 指到不存在的車輛 ID。

    Notes
    -----
    **配色要一次算好整段影片，不要每個影格各算各的。** 若在繪製時才依當下
    影格出現的車輛順序配色，同一台車的顏色會隨著其他車進出畫面而改變——
    畫面會閃爍，而且不會有任何錯誤訊息。:func:`~traffickit_viz.draw_boxes`
    因此要求顏色表涵蓋所有要畫的車輛，缺了就拋錯。
    """
    palette = tuple(tuple(item) for item in palette)
    if not palette:
        raise ValueError("palette 不可以是空的")

    ordered = list(dict.fromkeys(vehicle_ids))
    overrides = dict(overrides or {})
    unknown = sorted(set(overrides) - set(ordered))
    if unknown:
        raise ValueError(f"overrides 指定了不在 vehicle_ids 內的車輛：{unknown}")

    colors = {}
    for index, vehicle_id in enumerate(ordered):
        if vehicle_id in overrides:
            colors[vehicle_id] = parse_color(overrides[vehicle_id])
        else:
            colors[vehicle_id] = parse_color(palette[index % len(palette)])
    return colors


def _parse_color_string(spec: str) -> tuple[int, int, int]:
    text = spec.strip().lower()
    if not text:
        raise ValueError("顏色字串是空白")

    if text in NAMED_COLORS:
        return NAMED_COLORS[text]

    if text.startswith("#"):
        digits = text[1:]
        if len(digits) != 6:
            raise ValueError(f"無法解析顏色 {spec!r}，十六進位需為 #RRGGBB")
        try:
            red, green, blue = (int(digits[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            raise ValueError(f"無法解析顏色 {spec!r}，含非十六進位字元") from None
        return (blue, green, red)

    if "," in text:
        parts = [part.strip() for part in text.split(",")]
        if len(parts) != 3:
            raise ValueError(f"無法解析顏色 {spec!r}，RGB 需為三個數字")
        try:
            red, green, blue = (int(part) for part in parts)
        except ValueError:
            raise ValueError(f"無法解析顏色 {spec!r}，RGB 必須是整數") from None
        return tuple(_check_channel(value, spec) for value in (blue, green, red))

    raise ValueError(
        f"無法解析顏色 {spec!r}。可用寫法：名稱（{sorted(NAMED_COLORS)[:3]}…）、"
        f"'#RRGGBB' 或 'R,G,B'"
    )


def _check_channel(value, original) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"顏色 {original!r} 的分量 {value!r} 不是整數") from None
    if not 0 <= number <= 255:
        raise ValueError(f"顏色 {original!r} 的分量 {number} 超出 0–255")
    return number
