"""TrafficKit 的視覺化與影片輸出層。

目前提供的是**繪製層**：把 ``traffickit.formats`` 讀出來的逐影格軌跡畫成
車身框。讀寫影片檔與互動介面還沒搬進來。

為什麼獨立成一個套件
--------------------

``traffickit`` 只依賴 pandas 與 numpy，因此後端服務、CI 與 Jupyter 都裝得動。
視覺化需要 OpenCV（安裝後數百 MB），往後還會有 GUI。把這些放進核心，等於
讓每一個只想算轉向流量的人都被迫安裝一整套影像處理相依。

分工
----

======================  ==========================================
放這裡                  留在 ``traffickit``
======================  ==========================================
影片解碼與編碼          軌跡檔讀取（``traffickit.formats``）
bbox 繪製與疊圖         交通計算（``speed``、``volume``）
顏色、標籤、箭頭樣式    會改變交通結果意義的判定
比例尺（公尺 → 像素）   單位契約本身（m/s、秒、公尺）
互動介面與預覽          —
======================  ==========================================

判準是「這段邏輯改變的是**畫面**還是**數字**」。改變數字的留在核心，
改變畫面的放這裡。

相依方向是單向的：``traffickit_viz`` 可以 import ``traffickit``，
``traffickit`` 永遠不可以 import ``traffickit_viz``。核心的
``tests/test_layering.py`` 專門守這條線。

典型用法
--------

.. code-block:: python

    from traffickit.formats import read_motc_su_tracks
    from traffickit_viz import add_headings, assign_colors, BoxStyle, draw_boxes

    tracks = add_headings(read_motc_su_tracks("your_file_CSV_SU.csv"))
    wanted = ["1", "2", "3"]

    # 配色對整段影片一次算好，同一台車才不會在不同影格變色。
    style = BoxStyle(assign_colors(wanted), front="arrow")

    frame_boxes = tracks.query("vehicle_id in @wanted and frame == 100")
    draw_boxes(image, frame_boxes, style=style)   # image 就地被改
"""

from ._colors import (
    DEFAULT_PALETTE,
    NAMED_COLORS,
    assign_colors,
    color_to_hex,
    parse_color,
)
from ._draw import draw_boxes
from ._heading import CORNER_COLUMNS, add_headings
from ._style import FRONT_MODES, LABEL_MODES, BoxStyle, default_style

__version__ = "0.0.2"

__all__ = [
    "BoxStyle",
    "CORNER_COLUMNS",
    "DEFAULT_PALETTE",
    "FRONT_MODES",
    "LABEL_MODES",
    "NAMED_COLORS",
    "add_headings",
    "assign_colors",
    "color_to_hex",
    "default_style",
    "draw_boxes",
    "parse_color",
]
