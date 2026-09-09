"""輸入格式轉換層。

這一層**只做格式轉換**：把外部檔案讀成套件契約的欄位與型別，不做任何
交通判定。計算功能（traffickit.speed、traffickit.volume）維持零 I/O，
因此可以直接接收後端、資料庫或測試資料產生的 DataFrame。
"""

from ._motc_su import (
    DEFAULT_FPS,
    INCOMPLETE_CODE,
    MOTC_SU_VEHICLE_CLASSES,
    read_motc_su_passages,
    read_motc_su_tracks,
)

__all__ = [
    "DEFAULT_FPS",
    "INCOMPLETE_CODE",
    "MOTC_SU_VEHICLE_CLASSES",
    "read_motc_su_passages",
    "read_motc_su_tracks",
]
