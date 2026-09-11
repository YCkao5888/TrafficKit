"""介面背後的狀態與計算。

**這個模組完全不依賴 Qt**，因此可以單獨測試。視窗只負責把使用者的動作
轉成這裡的呼叫，再把結果畫到畫面上。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
from traffickit.formats import read_motc_su_tracks, read_motc_su_vehicles

from .._colors import assign_colors
from .._heading import add_headings
from .._resample import resample_tracks
from .._style import BoxStyle
from .._video import VideoInfo, probe_video

#: 車種代號 → 中文名稱，只用在介面顯示。
CLASS_NAMES = {
    "p": "行人", "u": "自行車", "m": "機車", "c": "汽車",
    "t": "貨車", "b": "巴士", "h": "聯結車頭", "g": "聯結車身",
}


@dataclass(frozen=True)
class Appearance:
    """介面上可調的選項。

    這是介面與 :class:`~traffickit_viz.BoxStyle` 之間的中介：BoxStyle 只管
    「一格怎麼畫」，這裡還包含補格與輸出的設定。
    """

    # 常用（主畫面）
    label: str = "id"
    front: str = "arrow"
    thickness: int = 2
    front_color: str = "white"

    # 進階（收在可展開的區塊）
    fill_alpha: float = 0.0
    font_scale: float = 0.6
    heading_window: int = 5
    interpolate: bool = True
    max_gap: int = 30
    show_frame_number: bool = False
    out_scale: float = 1.0
    codec: str = "MJPG"

    def replace(self, **changes) -> "Appearance":
        return replace(self, **changes)


@dataclass(frozen=True)
class LoadSummary:
    """載入軌跡檔之後，值得讓使用者一眼看到的數字。"""

    path: Path
    vehicle_count: int
    incomplete_count: int
    crosswalk_count: int
    first_frame: int
    last_frame: int
    class_counts: dict[str, int] = field(default_factory=dict)

    def describe(self) -> str:
        classes = "、".join(
            f"{CLASS_NAMES.get(code, code)} {count}"
            for code, count in sorted(
                self.class_counts.items(), key=lambda item: -item[1]
            )
        )
        return (
            f"{self.vehicle_count} 台車　影格 {self.first_frame}–{self.last_frame}　"
            f"不完整 {self.incomplete_count}　行穿線 {self.crosswalk_count}"
            + (f"　｜　{classes}" if classes else "")
        )


class Session:
    """一次操作的全部狀態：影片、軌跡、選取。"""

    def __init__(self) -> None:
        self.video: VideoInfo | None = None
        self.tracks: pd.DataFrame | None = None
        self.vehicles: pd.DataFrame | None = None

    # ---------------------------------------------------------------- 載入

    def load_video(self, path: str | os.PathLike[str]) -> VideoInfo:
        self.video = probe_video(path)
        return self.video

    def load_tracks(self, path: str | os.PathLike[str]) -> LoadSummary:
        """讀 MOTC_SU 軌跡檔，並把車種接到逐影格表上。

        車種是整台車的屬性，只存在於 ``read_motc_su_vehicles`` 那張表，
        但標籤要顯示它，所以在這裡接起來。
        """
        path = Path(path)
        tracks = read_motc_su_tracks(path)
        vehicles = read_motc_su_vehicles(path)

        self.tracks = tracks.merge(
            vehicles[["vehicle_id", "vehicle_class"]], on="vehicle_id", how="left"
        )
        self.vehicles = vehicles

        frames = tracks["frame"]
        return LoadSummary(
            path=path,
            vehicle_count=len(vehicles),
            incomplete_count=int((~vehicles["is_complete"]).sum()),
            crosswalk_count=int(vehicles["is_crosswalk"].sum()),
            first_frame=int(frames.min()) if len(frames) else 0,
            last_frame=int(frames.max()) if len(frames) else 0,
            class_counts=vehicles["vehicle_class"].value_counts().to_dict(),
        )

    @property
    def is_ready(self) -> bool:
        """影片與軌跡都有了嗎。"""
        return self.video is not None and self.tracks is not None

    # ---------------------------------------------------------------- 選取

    def style_for(
        self,
        vehicle_ids: list[str],
        appearance: Appearance,
    ) -> BoxStyle:
        """替選取的車輛建樣式。配色依**選取順序**，整段影片一致。"""
        return BoxStyle(
            assign_colors(vehicle_ids),
            label=appearance.label,
            front=appearance.front,
            thickness=appearance.thickness,
            front_color=appearance.front_color,
            fill_alpha=appearance.fill_alpha,
            font_scale=appearance.font_scale,
        )

    def suggested_range(self, vehicle_ids: list[str]) -> tuple[int, int]:
        """選取車輛出現的影格範圍，夾在影片長度內。"""
        if self.tracks is None or self.video is None:
            return (0, 0)
        last = max(0, self.video.frame_count - 1)
        chosen = self.tracks[self.tracks["vehicle_id"].isin(set(vehicle_ids))]
        if chosen.empty:
            return (0, last)
        frames = chosen["frame"]
        return max(0, int(frames.min())), min(last, int(frames.max()))

    # ------------------------------------------------------------ 取框

    def boxes_for_frame(
        self,
        frame: int,
        vehicle_ids: list[str],
        appearance: Appearance,
    ) -> pd.DataFrame:
        """某一格要畫的車輛框，補格與車頭方向都算好。

        Notes
        -----
        **只處理這一格附近的資料**：先把軌跡切到
        ``frame ± (heading_window + max_gap)`` 再補格，否則每拖一次時間軸
        都要對整份軌跡重算，上千台車的檔案會卡住。

        切片範圍要夠寬是因為車頭方向的平滑會看前後各 ``heading_window``
        格，而那些格本身可能是補出來的，補它們又需要更外圍的取樣點。
        """
        if self.tracks is None:
            return _empty_boxes()

        margin = appearance.heading_window + max(appearance.max_gap, 1)
        window = self._slice(vehicle_ids, frame - margin, frame + margin)
        if window.empty:
            return _empty_boxes()

        dense = resample_tracks(
            window,
            range(frame - appearance.heading_window,
                  frame + appearance.heading_window + 1),
            interpolate=appearance.interpolate,
            max_gap=appearance.max_gap,
        )
        if dense.empty:
            return _empty_boxes()

        dense = add_headings(dense, window=appearance.heading_window)
        return dense[dense["frame"] == frame].reset_index(drop=True)

    def dense_tracks(
        self,
        vehicle_ids: list[str],
        start: int,
        end: int,
        appearance: Appearance,
    ) -> pd.DataFrame:
        """整個輸出範圍的逐格資料，給輸出用。"""
        if self.tracks is None:
            return _empty_boxes()

        margin = appearance.heading_window + max(appearance.max_gap, 1)
        window = self._slice(vehicle_ids, start - margin, end + margin)
        if window.empty:
            return _empty_boxes()

        dense = resample_tracks(
            window,
            range(start, end + 1),
            interpolate=appearance.interpolate,
            max_gap=appearance.max_gap,
        )
        if dense.empty:
            return _empty_boxes()
        return add_headings(dense, window=appearance.heading_window)

    def _slice(self, vehicle_ids: list[str], low: int, high: int) -> pd.DataFrame:
        chosen = set(vehicle_ids)
        if not chosen:
            return _empty_boxes()
        tracks = self.tracks
        mask = (
            tracks["vehicle_id"].isin(chosen)
            & tracks["frame"].between(low, high)
        )
        return tracks.loc[mask]


def _empty_boxes() -> pd.DataFrame:
    columns = [
        "vehicle_id", "frame",
        "x1_px", "y1_px", "x2_px", "y2_px", "x3_px", "y3_px", "x4_px", "y4_px",
        "center_x_px", "center_y_px", "vehicle_class", "heading_x", "heading_y",
    ]
    return pd.DataFrame({name: pd.Series(dtype="object" if name in
                                         ("vehicle_id", "vehicle_class")
                                         else "float64")
                         for name in columns})


def describe_vehicle(row) -> str:
    """車輛清單上顯示的一行字。"""
    code = row["vehicle_class"]
    name = CLASS_NAMES.get(code, code)
    route = f"{row['entry_gate']}→{row['exit_gate']}"
    return f"{row['vehicle_id']}　{name}　{route}"


def parse_id_list(spec: str) -> list[str]:
    """``"2,4,5"`` 或 ``"10-15"`` → ID 清單，兩種寫法可混用。

    範圍寫法只在 ID 是整數時有意義；非整數的 ID 照字面處理。
    重複的只留第一次，順序維持輸入順序。
    """
    if not spec:
        return []

    result: list[str] = []
    for token in spec.replace(",", " ").split():
        parts = token.split("-")
        if len(parts) == 2 and all(part.strip().isdigit() for part in parts):
            low, high = int(parts[0]), int(parts[1])
            if high < low:
                low, high = high, low
            result.extend(str(value) for value in range(low, high + 1))
        else:
            result.append(token)
    return list(dict.fromkeys(result))


def summarise_id_list(vehicle_ids) -> str:
    """``["2","4","5","10","11","12"]`` → ``"2,4,5,10-12"``，是上面的反向。"""
    numeric = []
    other = []
    for item in vehicle_ids:
        (numeric if str(item).isdigit() else other).append(str(item))

    chunks = []
    ordered = sorted({int(value) for value in numeric})
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1] == ordered[end] + 1:
            end += 1
        if end - index >= 2:          # 連續三個以上才縮寫
            chunks.append(f"{ordered[index]}-{ordered[end]}")
        else:
            chunks.extend(str(value) for value in ordered[index:end + 1])
        index = end + 1
    return ",".join(chunks + sorted(other))
