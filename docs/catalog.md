# 交通功能目錄

本目錄是功能索引。詳細 I/O 以函式 docstring 為準；範例與測試提供可執行的證據。
新增功能時一併更新本檔。

- 安裝套件名：`traffickit`
- Python 匯入名：`traffickit`
- 套件版本以 `pyproject.toml` 為準；下表的「契約版」只記錄該功能 I/O 語意的版次。

> README.md 的教學使用 `traffic-analysis-demo` / `traffic_analysis` 作為示範名稱。
> 本專案實際採用的名稱是 `traffickit`，其餘結構與教學一致。

| 功能 ID | 公開入口 | 用途 | 負責人 | 契約版 | 狀態 |
| --- | --- | --- | --- | --- | --- |
| speed.speed_distribution | `traffickit.speed.summarise_speed_distribution` | 每車代表速度的分布統計與分箱 | 交付前填入姓名 | 1 | 試行 |
| speed.bin_edges | `traffickit.speed.speed_bin_edges` | 產生等寬分箱邊界（多群組共用） | 交付前填入姓名 | 1 | 試行 |

## speed.speed_distribution

- 必要資料：`vehicle_id`、`time_s`、`speed_smooth_mps`（m/s，已平滑）。
- 參數：
  - `bin_edges_mps`：必填，至少兩個嚴格遞增、有限、非負的邊界（m/s）。
  - `statistic`：`mean`（預設）／`median`／`max`／`p85`，每車代表速度的取法。
  - `moving_threshold_mps`：選填，樣本層移動門檻；`None` 表示不過濾。
- 輸出粒度：分箱一列一箱；`vehicle_speeds` 一列一車。**統計對象是車，不是樣本。**
- 分箱規則：`[lower, upper)`，最後一箱為 `[lower, upper]`。
- 統計母體：通過移動門檻後仍有樣本的所有車輛，**包含落在分箱範圍外的車輛**；
  `below_range_count` / `above_range_count` / `binned_vehicle_count` 分別可讀。
- 詳細規格：函式 docstring、`docs/worksheets/speed.speed_distribution.md`。
- 原始碼：`src/traffickit/speed/_distribution.py`。
- 範例：`examples/speed_distribution_demo.py`。
- 測試：`tests/test_speed_distribution.py`。
- 前置條件：速度已平滑並換算為 m/s；資料集內 `vehicle_id` 唯一；
  分析時段、ROI、車種與流向篩選由呼叫端先切好。
- 限制：不做平滑、不做像素／公尺換算、不自行分車種、不回傳箱形圖數列
  （呼叫端可用 `vehicle_speeds` 自行計算）。

## speed.bin_edges

- 參數：`width_mps`（> 0）、`upper_mps`（≥ `start_mps`）、`start_mps`（預設 0.0，≥ 0）。
- 輸出：`tuple[float, ...]`，最後一個邊界不小於 `upper_mps`。
- 用途：多個群組（車種、方向、時段）要畫在同一張圖時，先算一組共用邊界，
  再分別呼叫 `summarise_speed_distribution`，否則各組分箱不可比較。

## 指標與計算能力對照（後續整合用，尚未實作情境入口）

| 指標 ID | 使用功能 | 情境端提供的參數 |
| --- | --- | --- |
| （待填） | speed.speed_distribution | 分箱寬度、代表速度統計量、移動門檻、車種分組 |

情境入口仍須負責指標適用性、方向範圍與統計口徑。

## 與舊版 `data/speed_analyser.py` 的對照

舊版是後端服務類別，混合了資料存取、單位換算與呈現。本次只把「計算」搬進套件。

| 舊版行為 | 本套件的位置 | 差異說明 |
| --- | --- | --- |
| 由專案 metadata 取 `Scale`，`speed * scale * 3.6` | 呼叫端 | 核心一律接收 m/s；比例尺缺漏的擋門仍留在後端 |
| `speed_kmh > 7.2` 過濾樣本 | `moving_threshold_mps=2.0` | 單位改為 m/s；預設不過濾，需明確指定 |
| `movement_filters`、`filters` 流向篩選 | 呼叫端 | 欄位名稱（`in`/`out` 與 `entry`/`exit`）屬於資料來源差異 |
| `calc_method`：mean／max／median／q85 | `statistic`：mean／max／median／**p85** | 名稱改為 p85；語意相同（線性內插） |
| `min_speed` / `max_speed` 先過濾再統計 | `bin_edges_mps` 決定分箱範圍 | **範圍外的車不再從統計中消失**，改為分別計數 |
| `np.histogram` 後在最前面補一個 0 | `bins` 一列一箱 | 補 0 是繪圖庫的 X 軸慣例，屬於前端責任 |
| 單一車輛時 `std` 回傳 `0.0` | `std_mps` 回傳 `None` | 0 會被誤讀為「速度很一致」；未定義就回 None |
| 空資料回傳 `SpeedStats(0,0,0,0,0)` | 統計量為 `None`，分箱車輛數為 0 | 同上，避免「有資料且全為 0」與「沒有資料」混淆 |
| 分車種 `vehicle_grouping` 產生多組數列 | 呼叫端逐組呼叫，共用 `speed_bin_edges` | 車種對照表是專案設定，不是交通定義 |

**尚未做真實資料回歸比較。** 接回舊程式前，須用同一份資料、同一組平滑結果與門檻，
比對每車代表速度與各箱車輛數，並逐項確認上表的差異是預期的。
