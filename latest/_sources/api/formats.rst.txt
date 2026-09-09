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

前者一列一台車（進出閘門、車種、進出 frame），後者一列一台車一個 frame
（四角點與中心點）。兩者讀同一份檔，差別只在粒度。

常數
----

.. autodata:: MOTC_SU_VEHICLE_CLASSES
   :annotation:

.. autodata:: INCOMPLETE_CODE
   :annotation:

.. autodata:: DEFAULT_FPS
   :annotation:

.. note::

   不完整軌跡（代號 ``X``）會照樣讀入並標記 ``is_complete=False``，
   不會默默消失。要餵給 :func:`~traffickit.volume.summarise_turn_volume`
   之前請自行 ``.query("is_complete")``。

   完整的格式定義見 :doc:`../worksheets/formats.motc_su`。
