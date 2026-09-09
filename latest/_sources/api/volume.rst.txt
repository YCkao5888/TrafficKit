traffickit.volume
=================

.. currentmodule:: traffickit.volume

流量相關的交通計算。統計對象是**車次**，一列輸入計一次。

函式
----

.. autosummary::
   :toctree: generated/
   :nosignatures:

   summarise_turn_volume
   clockwise_movements

回傳型別
--------

.. autosummary::
   :toctree: generated/
   :nosignatures:

   TurnVolume
   TurnVolumeSummary

常數
----

.. autodata:: TURNS
   :annotation:

   本套件承認的轉向類別，同時也是輸出的排序順序。

.. autodata:: DEFAULT_VEHICLE_GROUPS
   :annotation:

.. autodata:: DEFAULT_PCU_WEIGHTS
   :annotation:

.. warning::

   ``DEFAULT_VEHICLE_GROUPS`` 與 ``DEFAULT_PCU_WEIGHTS`` 取自既有轉向流量
   調查 UI 的設定值，**本套件不認定其等同任何法規或手冊的規定值**。
   它們不是函式的預設值，必須明確傳入，實際採用哪一組權重由呼叫端決定並記錄。
