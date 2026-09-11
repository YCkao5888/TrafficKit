"""繪製樣式。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ._colors import parse_color

#: 標籤內容的選項。
LABEL_MODES = ("none", "id", "class", "both")

#: 車頭標示方式的選項。
FRONT_MODES = ("none", "edge", "arrow", "both")


@dataclass(frozen=True)
class BoxStyle:
    """一次繪製要用的所有外觀設定。

    Parameters
    ----------
    colors : mapping
        ``{車輛 ID: 顏色}``，顏色寫法同 :func:`~traffickit_viz.parse_color`。
        **必須涵蓋所有要畫的車輛**，通常由
        :func:`~traffickit_viz.assign_colors` 對整段影片一次算好。
    thickness : int, optional
        框線粗細（像素），至少 1。預設 2。
    label : {"none", "id", "class", "both"}, optional
        標籤內容。``"class"`` 與 ``"both"`` 需要 ``vehicle_class`` 欄位。
        預設 ``"id"``。
    font_scale : float, optional
        標籤字體大小，須大於 0。預設 0.6。
    fill_alpha : float, optional
        框內半透明填色，0 為不填、1 為不透明。預設 0.0。
    front : {"none", "edge", "arrow", "both"}, optional
        車頭標示方式。``"edge"`` 把車頭那條邊換色加粗；``"arrow"`` 從車身
        中心往前畫箭頭，需要 ``heading_x`` 與 ``heading_y`` 欄位
        （見 :func:`~traffickit_viz.add_headings`）。預設 ``"edge"``。
    front_color : str or sequence of int, optional
        車頭標示的顏色。預設白色。

    Raises
    ------
    ValueError
        選項不在允許清單內，或數值超出範圍。

    Notes
    -----
    這裡的每個參數都有預設值，與核心套件「不給預設門檻」的規則不同。
    兩者的差別在於**猜錯的後果**：核心的門檻猜錯會算出一個看起來正常的
    錯數字；這裡猜錯只是框線粗一點或標籤大一點，看一眼就知道要不要改。

    唯一沒有預設值的是 ``colors``，因為配色要對整段影片一次算好——
    詳見 :func:`~traffickit_viz.assign_colors` 的說明。

    ``edge`` 模式標出的是資料裡的車頭那條邊，車身框抖它就跟著抖；
    ``arrow`` 的方向經過時間平滑，明顯穩定得多。
    """

    colors: Mapping[str, tuple[int, int, int]]
    thickness: int = 2
    label: str = "id"
    font_scale: float = 0.6
    fill_alpha: float = 0.0
    front: str = "edge"
    front_color: tuple[int, int, int] = field(default=(255, 255, 255))

    def __post_init__(self) -> None:
        # frozen dataclass 不能直接指派，但在 __post_init__ 正規化是標準做法：
        # 早一點把顏色寫法轉成 BGR，錯的寫法在建立樣式時就會報錯，
        # 而不是等到畫到第 3000 個影格才炸。
        object.__setattr__(
            self, "colors",
            {str(key): parse_color(value) for key, value in self.colors.items()},
        )
        object.__setattr__(self, "front_color", parse_color(self.front_color))

        if not isinstance(self.thickness, int) or isinstance(self.thickness, bool):
            raise ValueError(f"thickness 必須是整數，收到 {self.thickness!r}")
        if self.thickness < 1:
            raise ValueError(f"thickness 必須至少是 1，收到 {self.thickness}")

        if self.label not in LABEL_MODES:
            raise ValueError(
                f"label {self.label!r} 不是可用選項，應為 {list(LABEL_MODES)}"
            )
        if self.front not in FRONT_MODES:
            raise ValueError(
                f"front {self.front!r} 不是可用選項，應為 {list(FRONT_MODES)}"
            )

        if not self.font_scale > 0:
            raise ValueError(f"font_scale 必須大於 0，收到 {self.font_scale}")
        if not 0.0 <= self.fill_alpha <= 1.0:
            raise ValueError(
                f"fill_alpha 必須介於 0 與 1 之間，收到 {self.fill_alpha}"
            )

    @property
    def needs_vehicle_class(self) -> bool:
        """這個樣式是否需要 ``vehicle_class`` 欄位。"""
        return self.label in ("class", "both")

    @property
    def needs_heading(self) -> bool:
        """這個樣式是否需要 ``heading_x`` 與 ``heading_y`` 欄位。"""
        return self.front in ("arrow", "both")

    def color_for(self, vehicle_id: str) -> tuple[int, int, int]:
        """取某台車的顏色；沒有指定就拋錯，不自己編一個。"""
        try:
            return self.colors[str(vehicle_id)]
        except KeyError:
            raise ValueError(
                f"顏色表裡沒有車輛 {vehicle_id!r}。"
                f"請用 assign_colors 對整段影片一次配好色再傳進來——"
                f"臨時補一個顏色會讓同一台車在不同影格變色。"
            ) from None


def default_style(
    vehicle_ids: Sequence[str],
    **options,
) -> BoxStyle:
    """用預設配色替一批車輛建一個樣式，是最常見的起手式。"""
    from ._colors import assign_colors

    return BoxStyle(assign_colors(vehicle_ids), **options)
