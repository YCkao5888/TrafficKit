traffickit.formats
==================

.. currentmodule:: traffickit.formats

輸入格式轉換層。**只做格式轉換**：把外部檔案讀成套件契約的欄位與型別，
不做任何交通判定（不推轉向、不算速度、不裁時段、不排除任何資料列）。

函式
----

.. autosummary::
   :toctree: generated/
   :nosignatures:

   read_motc_su_vehicles
   read_motc_su_tracks
   read_motc_ssam_vehicles
   read_motc_ssam_tracks

同一批空拍影像分析成果有兩種輸出版本，各有兩個入口：

.. list-table::
   :header-rows: 1

   * - 版本
     - 一列一台車
     - 一列一台車一個時間點
   * - Pixel Frame
     - :func:`read_motc_su_vehicles`
     - :func:`read_motc_su_tracks`
   * - SSAM
     - :func:`read_motc_ssam_vehicles`
     - :func:`read_motc_ssam_tracks`

``*_vehicles`` 給轉向流量用（進出閘門、車種、進出時間）；``*_tracks``
給逐點分析用（四角點與中心點）。同一版的兩個入口讀同一份檔，差別只在粒度。

兩版的差別在座標與時間軸：Pixel Frame 版是**像素**座標配 frame 編號，
SSAM 版是**公尺**座標配秒數，車身以車頭中點、車尾中點與車寬表示。
路口代號與車種代號兩版完全相同，因此 ``*_vehicles`` 的輸出都能直接餵給
:func:`~traffickit.volume.summarise_turn_volume`。

常數
----

.. autodata:: MOTC_SU_VEHICLE_CLASSES
   :annotation:

.. autodata:: INCOMPLETE_CODE
   :annotation:

.. autodata:: DEFAULT_FPS
   :annotation:

.. note::

   兩種代號不是路口代號，但都會照樣讀入並標記，不會默默消失：
   不完整軌跡（``X``）標 ``is_complete=False``；
   行人與自行車走的行穿線（兩個路口字母，例如 ``AB``）標
   ``is_crosswalk=True``。要餵給
   :func:`~traffickit.volume.summarise_turn_volume` 之前請自行
   ``.query("is_complete and not is_crosswalk")``。

   完整的格式定義見 :doc:`../worksheets/formats.motc_su` 與
   :doc:`../worksheets/formats.motc_ssam`。
