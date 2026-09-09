# 工作單：speed.speed_distribution

依 [`feature-development-guide.md`](../feature-development-guide.md)
「每個新功能都要填的一張工作單」填寫。

- **功能 ID**：speed.speed_distribution
- **一句目的**：給定同一份資料集內已完成速度平滑的軌跡資料與分箱邊界，
  求出每台車的代表速度並統計其分布。
- **主要負責人**：yckao
- **契約版**：1
- **狀態**：試行（升級條件見 [`catalog.md`](../catalog.md) 的「狀態」）
- **公開函式入口**：`traffickit.speed.summarise_speed_distribution`
  （輔助：`traffickit.speed.speed_bin_edges`）

## 必要輸入

`pandas.DataFrame`，一列是一台車在一個時間點的資料。

| 欄位 | 型別 | 單位／基準 | 規則 |
| --- | --- | --- | --- |
| `vehicle_id` | 字串 | 同一資料集內的車輛 ID | 非空白、無缺值；同一車須使用相同 ID |
| `time_s` | 實數 | 相對本資料集共同起點的秒數 | 有限、非負、無缺值 |
| `speed_smooth_mps` | 實數 | m/s | 已完成平滑；有限、非負、無缺值 |

補充約定：

- 一次呼叫只包含一個 ID 不衝突的資料集。
- `(vehicle_id, time_s)` 不可重複；原始列索引可以重複，函式不依賴它。
- 允許未排序、允許其他欄位；其他欄位不參與計算也不會出現在輸出。
- 數字字串（例如 `"12.5"`）由資料轉換端先轉成數值，核心不猜型別。
- `time_s` 目前只用於重複樣本檢查與維持契約一致，不參與計算。
  取樣間隔不等距時，`mean` 會偏向取樣密集的路段；需要時間加權須另立功能。

## 參數

| 參數 | 型別 | 預設 | 意義與範圍 |
| --- | --- | --- | --- |
| `bin_edges_mps` | 數值序列 | 無（必填） | 至少 2 個、嚴格遞增、有限、非負的邊界，單位 m/s |
| `statistic` | 字串 | `"mean"` | 每車代表速度：`mean`／`median`／`max`／`p85` |
| `moving_threshold_mps` | 實數或 None | `None` | 樣本層門檻，只保留**嚴格大於**門檻的樣本 |

`bin_edges_mps` 不給預設值，避免呼叫端忘記設定時套用不適用的分箱。
`p85` 為 pandas 預設的線性內插分位數。

## 輸出

回傳 `SpeedDistribution`（frozen dataclass）：

| 屬性 | 型別 | 內容 |
| --- | --- | --- |
| `bins` | DataFrame | `bin_index`(int64)、`lower_mps`、`upper_mps`、`vehicle_count`(int64)、`proportion` |
| `vehicle_speeds` | DataFrame | `vehicle_id`(string)、`sample_count`(int64)、`speed_mps`；依 ID 字串排序 |
| `summary` | `SpeedSummary` | `vehicle_count`、`mean_mps`、`std_mps`、`min_mps`、`median_mps`、`p85_mps`、`max_mps` |
| `statistic` | str | 本次採用的統計量 |
| `moving_threshold_mps` | float 或 None | 本次採用的移動門檻 |
| `input_vehicle_count` | int | 套用移動門檻**之前**的車輛數 |
| `binned_vehicle_count` | int | 落入分箱範圍的車輛數（直方圖分母） |
| `below_range_count` / `above_range_count` | int | 低於／高於分箱範圍的車輛數 |

`below + binned + above == summary.vehicle_count`。

## 判定規則

1. 驗證輸入與參數；任何無效值一律拋錯，不默默排除。
2. 給定 `moving_threshold_mps` 時，只保留 `speed_smooth_mps > threshold` 的樣本；
   過濾後沒有樣本的車輛整台排除。
3. 依 `statistic` 把每台車收斂成一個代表速度。
4. 依 `bin_edges_mps` 分箱，分箱為 `[lower, upper)`，**最後一箱為 `[lower, upper]`**。
5. 落在範圍外的車輛不進分箱，改記入 `below_range_count` / `above_range_count`。
6. `proportion` 的分母是 `binned_vehicle_count`；分母為 0 時所有 proportion 為 0.0。

## 前置條件

- 速度已完成平滑，並已由呼叫端換算為 m/s（像素／公尺比例尺不在本功能內）。
- 分析時段、ROI、流向、車種等篩選由呼叫端先切好子集合。
- 多群組比較時，先用 `speed_bin_edges` 取得一組共用邊界再逐組呼叫。

## 品質政策

| 情況 | 本功能行為 |
| --- | --- |
| 缺必要欄位、重複欄名、重複樣本、無效數值、無效參數 | 拋 `ValueError`，訊息指出欄位或參數名稱 |
| 傳入的不是 DataFrame | 拋 `TypeError` |
| 有必要欄位但沒有資料列 | 回傳固定 schema：各箱車輛數 0、統計量 `None` |
| 移動門檻過濾後沒有任何車輛 | 與空輸入相同的 schema，但 `input_vehicle_count` 保留原車輛數 |
| 只有一台車 | `std_mps` 為 `None`（不以 0.0 代替） |
| 代表速度落在分箱範圍外 | 不進分箱，但仍計入 `summary` 與範圍外計數 |
| 函式執行完成 | 不修改原始輸入、不讀寫檔案 |

## 統計口徑

- 計數對象：**車**。一台車在資料中不論有幾個樣本，只計一次。
- 直方圖分母：`binned_vehicle_count`。
- `summary` 分母：`summary.vehicle_count`（含範圍外的車）。
- 時間範圍：呼叫端傳入的全部資料範圍；本功能不裁切。

## 手算範例

資料（速度單位 m/s，見 `examples/speed_distribution_demo.py`）：

| 車輛 | 時間（秒） | 平滑速度 | mean | median | max | p85 |
| --- | --- | --- | --- | --- | --- | --- |
| A | 0、1、2 | 8、9、10 | 9 | 9 | 10 | 9.7 |
| B | 0、1、2 | 9、11、12 | 32/3 ≈ 10.667 | 11 | 12 | 11.7 |
| C | 0、1、2 | 11、11、9 | 31/3 ≈ 10.333 | 11 | 11 | 11 |
| D | 0、1 | 0.5、1.5 | 1 | 1 | 1.5 | 1.35 |

**案例一（成立）**：`statistic="mean"`、`bin_edges_mps=(0, 5, 10, 15)`

| bin | 範圍 | 車輛 | 車輛數 | 比例 |
| --- | --- | --- | --- | --- |
| 0 | [0, 5) | D | 1 | 0.25 |
| 1 | [5, 10) | A | 1 | 0.25 |
| 2 | [10, 15] | B、C | 2 | 0.50 |

`summary`：車輛數 4、平均 7.75、中位數 29/3 ≈ 9.667、P85 ≈ 10.517、
最大 32/3 ≈ 10.667、標準差 ≈ 4.5572（樣本標準差，ddof=1）。

**案例二（不成立／被排除）**：加上 `moving_threshold_mps=2.0`

D 的兩個樣本都不大於 2，整台排除。`input_vehicle_count` 仍為 4，
`summary.vehicle_count` 為 3，各箱車輛數 `[0, 1, 2]`，比例 `[0, 1/3, 2/3]`。

**案例三（邊界）**：`statistic="max"`、`bin_edges_mps=(0, 5, 10)`

A 的最大值剛好等於最後一個邊界 10，落入最後一箱 `[5, 10]`；
B（12）與 C（11）超出範圍，`above_range_count = 2`，`binned_vehicle_count = 2`。

## 原始碼／範例／測試位置

- 原始碼：`src/traffickit/speed/_distribution.py`
- 範例：`examples/speed_distribution_demo.py`
- 測試：`tests/test_speed_distribution.py`（24 個測試）

## 驗證環境與版本

| 項目 | 內容 |
| --- | --- |
| 日期 | 2026-09-09 |
| 狀態 | 試行（尚未做真實資料回歸比較） |
| 套件版本 | traffickit 0.1.0 |
| OS | Windows 11 Pro 10.0.26200 |
| Python | 3.10.5 |
| 相依套件 | pandas 2.3.3、numpy 2.2.6（見 `requirements-validated.txt`） |
| 可編輯安裝與範例 | 成功；四台車的分箱與統計和手算一致 |
| 規格測試 | 本功能 24 個測試全部通過（當時全專案 24 個） |
| wheel 建置 | 成功產生 `dist/traffickit-0.1.0-py3-none-any.whl` |
| 另一個虛擬環境安裝 wheel | 成功（`.venv-check`）；確認匯入已安裝版本，再次通過範例與 24 個測試 |
| 效能 | 300,000 列／5,000 台車，`mean` 與 `p85` 皆約 0.20 秒（上述環境，單次量測） |

`requirements-validated.txt` 只記錄本次實際安裝的版本；其中 traffickit 記為本機
wheel 路徑，不能直接當成可搬移的部署鎖檔。

## 舊程式差異與已知限制

- 與舊版 `data/speed_analyser.py`（本機參考，未納入版控）的逐項差異見 `docs/catalog.md`；該表已完整記錄比對結果，不需要原檔。
- **尚未做真實資料回歸比較**，接回舊程式前必須補。
- 尚未驗證：Linux／macOS、其他 pandas 版本、超過百萬列的資料。
- 尚未提供：速度平滑、時間加權平均、箱形圖數列、車種分組入口。
