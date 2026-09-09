# 交通功能目錄

本目錄是功能索引。詳細 I/O 以函式 docstring 為準；範例與測試提供可執行的證據。
新增功能時一併更新本檔，並補一份 `docs/worksheets/<功能 ID>.md` 工作單。

- 安裝套件名／Python 匯入名：`traffickit`
- 套件版本以 `pyproject.toml` 為準；下表的「契約版」只記錄該功能 I/O 語意的版次。
- 開發格式見 [`feature-development-guide.md`](feature-development-guide.md)。

分層：`traffickit.speed`、`traffickit.volume` 是**計算層**，零 I/O；
`traffickit.formats` 是**格式轉換層**，可以讀檔，但只做欄位與型別轉換，
不做任何交通判定。

| 功能 ID | 公開入口 | 用途 | 負責人 | 契約版 | 狀態 |
| --- | --- | --- | --- | --- | --- |
| speed.speed_distribution | `traffickit.speed.summarise_speed_distribution` | 每車代表速度的分布統計與分箱 | yckao | 1 | 試行 |
| speed.bin_edges | `traffickit.speed.speed_bin_edges` | 產生等寬分箱邊界（多群組共用） | yckao | 1 | 試行 |
| volume.turn_volume | `traffickit.volume.summarise_turn_volume` | 各進入方向 × 轉向 × 車種分組的車輛數與 PCU | yckao | 1 | 試行 |
| volume.clockwise_movements | `traffickit.volume.clockwise_movements` | 由順時針路口代號推導轉向對照表 | yckao | 1 | 試行 |
| formats.motc_su | `traffickit.formats.read_motc_su_vehicles`、`read_motc_su_tracks` | 讀取 MOTC_SU 空拍影像軌跡 CSV | yckao | 1 | 試行 |

## 欄位定義

### 負責人

填實際能回答「這個交通定義為什麼這樣訂」的人，不填「待補」。
新增功能時由提出需求的人指定；交接時同時更新本表與該功能的工作單。

### 契約版

從 1 開始的整數，只記錄**這個功能**的 I/O 語意版次，與套件版本無關。

| 變更內容 | 契約版 |
| --- | --- |
| 新增／移除／改名輸入欄位或參數 | +1 |
| 改變輸出欄位、型別或排序 | +1 |
| 改變判定規則、邊界比較、同值選取、統計口徑或分母 | +1 |
| 新增**可選**參數且預設行為完全不變 | 不變（但要在工作單註明新增時機） |
| 只改內部實作、效能、註解或錯誤訊息措辭 | 不變 |

契約版 +1 時，必須同步更新工作單、範例、測試，並在下方「契約變更紀錄」列出差異。

### 狀態

四階段。**升級條件全部達成才可改狀態，不可提前。**

| 狀態 | 進入條件 | 呼叫端可以期待什麼 |
| --- | --- | --- |
| 草擬 draft | 契約還在討論 | 不要呼叫；介面隨時會改，可能整個砍掉 |
| 試行 trial | 契約定稿；範例與測試通過；工作單完成（含驗證環境與效能紀錄）；wheel 在乾淨環境安裝後可用 | 可以用。介面仍可能變，但變更會通知並升契約版 |
| 正式 stable | 試行的全部條件，**加上**：①真實資料回歸比較完成並記錄差異 ②至少一個實際呼叫端（後端／桌面程式／情境入口）在用 ③負責人確認 | 契約凍結。要改就升契約版並列出差異，且需通知已知呼叫端 |
| 淘汰 deprecated | 已有替代功能，且替代品至少為「試行」 | 只修 bug，不加功能。本表指向替代品，預計移除時間寫在工作單 |

降級也可能發生：正式功能若發現契約有誤，先降回試行再修，不要在正式狀態下悄悄改語意。

**目前五個功能都是「試行」，卡在真實資料回歸比較尚未執行。**
補上比較紀錄、並確認差異都是預期的之後，即可升為「正式」。
`volume.turn_volume` 另缺後端舊版計算的原始碼，目前只能與前端所呈現的行為比對。

## 契約變更紀錄

| 日期 | 功能 ID | 契約版 | 變更內容 | 對呼叫端的影響 |
| --- | --- | --- | --- | --- |
| 2026-09-09 | speed.speed_distribution | 1 | 初版 | — |
| 2026-09-09 | speed.bin_edges | 1 | 初版 | — |
| 2026-09-09 | volume.turn_volume | 1 | 初版（發行前把第一個參數 `passages` 更名為 `vehicles`） | — |
| 2026-09-09 | volume.clockwise_movements | 1 | 初版 | — |
| 2026-09-09 | formats.motc_su | 1 | 初版（發行前調整兩處：`fps` 預設由 10 改成實際速率 9.99；`read_motc_su_passages` 更名為 `read_motc_su_vehicles`） | — |

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

## volume.turn_volume

- 必要資料：
  - `vehicles`（一列一台車）：`vehicle_id`（唯一）、`entry_gate`、`exit_gate`、`vehicle_class`。
  - `movements`（路口轉向定義）：`entry_gate`、`exit_gate`、`turn`、`is_allowed`。
- 參數：`vehicle_groups`（分組 → 車種，順序即報表欄位順序）、
  `pcu_weights`（分組 → {轉向: 權重}），兩者皆必填。
- 轉向類別只接受 `left`／`straight`／`right`／`u_turn`（模組常數 `TURNS`）。
- 輸出粒度：`movements` 一列 = 進入 × 駛出 × 轉向 × 分組；
  `by_turn` 一列 = 進入 × 轉向 × 分組。**合法但 0 台的組合會保留**，
  與 `is_allowed=False`（不允許轉）是不同狀態。
- 統計口徑：計數對象是車次；未被分組涵蓋的車種不計入，但記在
  `summary.unassigned_*`；違規轉向照實計數並記在 `summary.disallowed_vehicle_count`。
- 詳細規格：函式 docstring、`docs/worksheets/volume.turn_volume.md`。
- 原始碼：`src/traffickit/volume/_turn_volume.py`。
- 範例：`examples/turn_volume_demo.py`。
- 測試：`tests/test_turn_volume.py`。
- 前置條件：進出閘門已判定、時段與區域已由呼叫端切好、車種代碼已統一。
- 限制：不判定進出閘門、不切時段、不算百分比與小計、不匯出 CSV；
  同一台車多次通過需給不同 `vehicle_id`。
- 常數：`DEFAULT_VEHICLE_GROUPS`、`DEFAULT_PCU_WEIGHTS` 取自舊版 UI 設定，
  **必須明確傳入**，本套件不認定其等同任何法規或手冊的規定值。

## volume.clockwise_movements

- 用途：產生 `summarise_turn_volume` 需要的 `movements` 對照表。
- 參數：`gates`（**依順時針排列**的路口代號，非空白、不重複、數量須為偶數）、
  `disallowed`（不允許的 (進入, 駛出) 組合）。
- 判定規則：`offset = (j - i) mod n`；0 → `u_turn`、`n/2` → `straight`、
  小於 `n/2` → `left`、其餘 → `right`。
  依據是「順時針編號時，下一個分支就在駛入車輛的左手邊」。
- 適用來源：MOTC_SU 的 A/B/C/D 就是順時針編號，可直接使用。
- **限制：只推導幾何類別，不知道現場管制。** 產生的表格預設全部
  `is_allowed=True`，這在多數路口是錯的（尤其迴轉），必須自行填 `disallowed`。
  奇數分支（五岔路口）沒有正對面的分支 → 拋錯，請自行撰寫對照表。
  分支非等角分布（歪斜路口、Y 型路口）時結果可能與現場認知不同。
- 原始碼：`src/traffickit/volume/_movements.py`；測試：`tests/test_motc_su.py`。

## formats.motc_su

- 用途：讀取 MOTC_SU 空拍影像軌跡 CSV（無標題列、每列長度不一）。
- 兩個入口：`read_motc_su_vehicles`（一列一台車，給轉向流量用）、
  `read_motc_su_tracks`（一列一台車一個 frame，含四角點與中心點，像素單位）。
- 參數：`path`、`fps`（預設 9.99 = 29.97/3 的實際拍攝速率；格式定義文件
  寫的是整數 10）、`encoding`（預設 utf-8）。
- **不完整軌跡（代號 X）照樣讀入並標記 `is_complete=False`**，不默默丟掉；
  要餵給 `summarise_turn_volume` 前請自行 `.query("is_complete")`。
- 一律驗證「軌跡值數 = 8 × frame 數」，錯位或截斷的檔案會拋錯並指出行號。
- 詳細規格與格式定義：`docs/worksheets/formats.motc_su.md`。
- 原始碼：`src/traffickit/formats/_motc_su.py`；範例：`examples/motc_su_turn_volume_demo.py`。
- 限制：h（聯結車車頭）與 g（車身）是同一輛車的兩列，本讀取器不合併；
  統計時把 g 留在車種分組之外，它會出現在 `unassigned_classes`。

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

## 與舊版 `data/TurnVolumeAnalysis.vue` 的對照

**該檔是前端元件，不含計算**；計算在後端 `getTurnVolumeReport` 端點，其原始碼未取得。
以下是與前端所呈現行為的比對，不是與後端算法逐行比對。完整表格見
[`worksheets/volume.turn_volume.md`](worksheets/volume.turn_volume.md)。

| 舊版行為（前端所見） | 本套件 | 差異說明 |
| --- | --- | --- |
| 後端回傳 `result[進入][轉向][分組] = {count, pcu}` | `by_turn` 長格式表 | 巢狀字典改成表格，資訊等價 |
| 前端 `movements.some(...)` 算 `allowed_turns` | `by_turn.is_allowed`（取 any） | 判定規則相同，改由套件計算 |
| 只有轉向層級 | 多一張 `movements` 表保留 `exit_gate` | 兩個出口同屬右轉時可拆開 |
| 未定義的 (from,to) 行為不明 | 拋 `ValueError` | 不要靜靜算出一份少了車的報表 |
| 未分組車種默默不見 | 記入 `summary.unassigned_*` | 分母要說得清楚 |
| 違規轉向行為不明 | 照實計數並標記 | 這是真實資訊，不應被隱藏 |
| PCU 權重寫死在前端 `DEFAULT_GROUPS` | 必填參數，另提供 `DEFAULT_PCU_WEIGHTS` 常數 | 權重是案件設定，不是演算法 |
| 百分比、小計、總計、CSV 在前端 | 不提供 | 版面與輸出屬於應用端 |

**尚未取得後端算法，也尚未做真實資料回歸比較。** 接回舊系統前必須補其中之一。
