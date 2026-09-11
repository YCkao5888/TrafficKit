"""輸入格式轉換層。

這一層**只做格式轉換**：把外部檔案讀成套件契約的欄位與型別，不做任何
交通判定。計算功能（traffickit.speed、traffickit.volume）維持零 I/O，
因此可以直接接收後端、資料庫或測試資料產生的 DataFrame。
"""

from ._motc_common import INCOMPLETE_CODE, MOTC_SU_VEHICLE_CLASSES
from ._motc_ssam import read_motc_ssam_tracks, read_motc_ssam_vehicles
from ._motc_su import DEFAULT_FPS, read_motc_su_tracks, read_motc_su_vehicles

__all__ = [
    "DEFAULT_FPS",
    "INCOMPLETE_CODE",
    "MOTC_SU_VEHICLE_CLASSES",
    "read_motc_ssam_tracks",
    "read_motc_ssam_vehicles",
    "read_motc_su_tracks",
    "read_motc_su_vehicles",
]
