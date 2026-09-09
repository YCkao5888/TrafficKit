API reference
=============

TrafficKit 的公開介面。**只有這裡列出的名稱是公開契約**；底線開頭的模組
（例如 ``traffickit.speed._distribution``）是內部實作，隨時可能改變。

分層
----

.. list-table::
   :header-rows: 1
   :widths: 30 45 25

   * - 子套件
     - 責任
     - 可以讀檔？
   * - :doc:`traffickit.speed <speed>`
     - 速度相關的交通計算
     - 否
   * - :doc:`traffickit.volume <volume>`
     - 流量相關的交通計算
     - 否
   * - :doc:`traffickit.formats <formats>`
     - 外部檔案 → 套件契約的表格
     - 是，但只做欄位與型別轉換

計算層不讀寫檔案、不連資料庫、不 print，因此可以直接接後端、資料庫查詢
或測試資料產生的 ``DataFrame``。

.. toctree::
   :maxdepth: 2

   speed
   volume
   formats

閱讀 docstring 的方式
---------------------

每個函式的說明都遵循同一組段落：

Parameters
   每個參數的型別、單位與有效範圍。單位一律寫在欄位名或參數名的後綴
   （``_mps``、``_s``、``_px``）。

Returns
   輸出的欄位、型別與排序規則。回傳多張表時會用 frozen dataclass 包起來。

Raises
   什麼情況拋 ``TypeError``、什麼情況拋 ``ValueError``。
   **本套件不默默排除無效資料**，不合規格一律拋錯。

Notes
   **這個功能不做什麼**，以及與交通定義有關的注意事項（分母、邊界比較、
   同值取捨）。這一段通常比 Parameters 更重要。

更完整的契約、手算範例與驗證紀錄在對應的
:doc:`工作單 <../worksheets/index>`。
