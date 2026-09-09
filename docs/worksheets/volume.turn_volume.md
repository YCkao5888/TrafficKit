# 工作單：volume.turn_volume

依 [`feature-development-guide.md`](../feature-development-guide.md)
「每個新功能都要填的一張工作單」填寫。

- **功能 ID**：volume.turn_volume
- **一句目的**：給定一份「一列一台車」的通過紀錄與路口的轉向定義，
  統計各進入方向、各轉向、各車種分組的車輛數與 PCU。
- **主要負責人**：yckao
- **公開函式入口**：`traffickit.volume.summarise_turn_volume`
- **契約版**：1
- **狀態**：試行（尚未與後端舊版計算逐項比對）
- **參考來源**：`data/TurnVolumeAnalysis.vue`（本機參考，未納入版控）（**僅前端 UI，不含計算**；
  提供輸出契約、轉向類別、車種代碼與 PCU 權重預設值）

## 必要輸入

### `vehicles`：一列一台車的通過紀錄

| 欄位 | 型別 | 規則 |
| --- | --- | --- |
| `vehicle_id` | 字串 | 非空白、**不可重複** |
| `entry_gate` | 字串 | 非空白，進入閘門代碼 |
| `exit_gate` | 字串 | 非空白，駛出閘門代碼 |
| `vehicle_class` | 字串 | 非空白，車種代碼（例如 c／m／b／t／h／p） |

補充約定：

- 允許未排序、允許其他欄位；列索引可以重複，函式不依賴它。
- 同一台車若在資料範圍內通過兩次，呼叫端須給不同的 `vehicle_id`
  （或先切成兩份資料）。本版沒有「同一台車多次通過」的概念。
- **軌跡 → 進出閘門的判定不在本功能內。** ROI 幾何、跨線方向、
  重複進出的處理是另一組定義，應由另一個功能負責。

### `movements`：路口的轉向定義

| 欄位 | 型別 | 規則 |
| --- | --- | --- |
| `entry_gate` | 字串 | 非空白 |
| `exit_gate` | 字串 | 非空白 |
| `turn` | 字串 | 只接受 `left`／`straight`／`right`／`u_turn` |
| `is_allowed` | 布林 | 必須是布林欄位，不接受 0／1 |

- 至少一列；`(entry_gate, exit_gate)` 不可重複。
- 這張表同時決定三件事：轉向類別怎麼查、報表要列出哪些格子、
  哪些轉向合法。
- 客戶端設定（舊版 `TurnDirection[zone].movements` 的
  `from`／`to`／`category`／`is_allowed`）由整合端轉成上述欄位名稱，
  轉換寫法見 `examples/turn_volume_demo.py` 的 `load_movements()`。

## 參數

| 參數 | 型別 | 預設 | 意義 |
| --- | --- | --- | --- |
| `vehicle_groups` | Mapping[str, Iterable[str]] | 無（必填） | 分組名稱 → 車種代碼。同一車種不可跨組。**宣告順序即報表欄位順序。** |
| `pcu_weights` | Mapping[str, Mapping[str, float]] | 無（必填） | 分組名稱 → {轉向: 權重}。每組都要涵蓋 `movements` 中出現的每個轉向；有限、非負。 |

不提供預設權重。需要舊版 UI 的那組值時，明確傳入模組常數
`DEFAULT_VEHICLE_GROUPS` 與 `DEFAULT_PCU_WEIGHTS`——
**它們只是既有程式的設定值，本套件不認定其等同任何法規或手冊的規定值。**

## 輸出

回傳 `TurnVolume`（frozen dataclass）：

| 屬性 | 型別 | 內容 |
| --- | --- | --- |
| `movements` | DataFrame | 最細粒度，一列 = 進入 × 駛出 × 轉向 × 分組 |
| `by_turn` | DataFrame | 報表用，一列 = 進入 × 轉向 × 分組（駛出加總） |
| `summary` | `TurnVolumeSummary` | 分母與例外計數 |
| `vehicle_groups` | tuple[str, ...] | 本次分組順序 |
| `turns` | tuple[str, ...] | 本次出現的轉向，依 `TURNS` 順序 |

兩張表的欄位：

| 欄位 | 型別 | 意義 |
| --- | --- | --- |
| `entry_gate` / `exit_gate` / `turn` / `vehicle_group` | string | 分類鍵（`by_turn` 無 `exit_gate`） |
| `is_allowed` | bool | 該轉向是否允許；`by_turn` 為「任一駛出閘門允許即 True」 |
| `vehicle_count` | int64 | 車輛數 |
| `pcu_weight` | float64 | 本次採用的權重 |
| `pcu` | float64 | `vehicle_count * pcu_weight` |

`TurnVolumeSummary`：`input_vehicle_count`、`counted_vehicle_count`、
`total_pcu`、`unassigned_vehicle_count`、`unassigned_classes`、
`disallowed_vehicle_count`。

`input_vehicle_count == counted_vehicle_count + unassigned_vehicle_count`。

排序：`entry_gate` 字串序 → `turn` 依 `TURNS` 固定順序 →
`exit_gate` 字串序 → 分組依宣告順序。

## 判定規則

1. 驗證兩張表與兩個參數；任何無效值一律拋錯。
2. 依 `vehicle_class` 對照 `vehicle_groups` 得到分組；對不到的車輛不計入統計。
3. 資料中出現 `movements` 未定義的 `(entry_gate, exit_gate)` → 拋 `ValueError`。
4. 以 `movements × vehicle_groups` 展開成完整格子，**沒有車的組合保留為 0**。
5. `pcu = vehicle_count × pcu_weights[分組][轉向]`，不四捨五入。
6. `by_turn` 把 `exit_gate` 加總；`is_allowed` 取 `any`。

## 前置條件

- 進出閘門已判定完成，且時段、區域（zone）已由呼叫端切好。
- 車種代碼已統一（大小寫、空白由資料轉換端處理）。

## 品質政策

| 情況 | 本功能行為 |
| --- | --- |
| 缺必要欄位、重複欄名、空白字串、重複 `vehicle_id`、重複 `(entry, exit)` | 拋 `ValueError`，訊息指出欄位名稱 |
| `vehicles` 或 `movements` 不是 DataFrame | 拋 `TypeError` |
| `turn` 不在四個合法值內、`is_allowed` 不是布林 | 拋 `ValueError` |
| 資料出現未定義的 `(entry, exit)` | 拋 `ValueError`，列出前 5 組 |
| 車種未被任何分組涵蓋 | **不計入統計**，記入 `unassigned_vehicle_count` 與 `unassigned_classes` |
| `is_allowed=False` 卻有車 | 照實計數並標記，記入 `disallowed_vehicle_count`（可視為違規轉向） |
| 合法但沒有車的轉向 | 保留為 0，不從表中消失 |
| `vehicles` 沒有資料列 | 回傳完整格子、全部為 0；`movements` 為空則拋錯 |
| 函式執行完成 | 不修改原始輸入、不讀寫檔案 |

## 統計口徑

- 計數對象：**車次**。一列 `vehicles` 計一次。
- `movements` 表的分母：`movements × vehicle_groups` 的完整格子。
- `summary.total_pcu` 的分母：納入統計（已分組）的車輛。
- 百分比不在本功能內。舊版報表用「該進入方向的自身總計」當分母，
  這是版面選擇；要換成「全路口總計」只需改呼叫端的 groupby。

## 手算範例

轉向定義（N 有兩個右轉出口；E→E 迴轉不允許）：

| entry | exit | turn | is_allowed |
| --- | --- | --- | --- |
| N | E | left | True |
| N | S | straight | True |
| N | W | right | True |
| N | NE | right | True |
| E | N | right | True |
| E | W | straight | True |
| E | E | u_turn | **False** |

通過紀錄（8 台）：V1 N→S c、V2 N→S c、V3 N→S m、V4 N→E c、
V5 E→W m、V6 E→E m、V7 N→S **p**、V8 N→NE c

分組：小型車 = {c}、機車 = {m}；權重取 `DEFAULT_PCU_WEIGHTS` 的對應兩組。

**案例一（成立）**：`movements` 表共 7 × 2 = 14 列，非零的是

| entry | exit | turn | 分組 | 車輛數 | 權重 | PCU |
| --- | --- | --- | --- | --- | --- | --- |
| N | E | left | 小型車 | 1 | 1.05 | 1.05 |
| N | S | straight | 小型車 | 2 | 1.00 | 2.00 |
| N | S | straight | 機車 | 1 | 0.42 | 0.42 |
| N | NE | right | 小型車 | 1 | 1.08 | 1.08 |
| E | W | straight | 機車 | 1 | 0.42 | 0.42 |
| E | E | u_turn | 機車 | 1 | 0.43 | 0.43 |

`summary`：輸入 8、納入 7、未分組 1（車種 `p`）、違規轉向 1、總 PCU 5.40。

**案例二（合法但 0 台，不可消失）**：E→N 右轉允許但沒有車，
`movements` 表仍有兩列（兩個分組）車輛數 0、`is_allowed=True`。
這與 E→E 的 `is_allowed=False` 是不同狀態，報表才能一個顯示 0、一個顯示「-」。

**案例三（邊界／彙整）**：`by_turn` 的 (N, right) 把 N→W 的 0 台與
N→NE 的 1 台合成一列 → 小型車 1 台、PCU 1.08。
若只看 `by_turn` 會看不出是哪個出口，這是刻意的取捨，需要細節時看 `movements`。

## 原始碼／範例／測試位置

- 原始碼：`src/traffickit/volume/_turn_volume.py`（共用驗證在 `src/traffickit/_validation.py`）
- 範例：`examples/turn_volume_demo.py`
- 測試：`tests/test_turn_volume.py`（23 個測試）

## 驗證環境與版本

| 項目 | 內容 |
| --- | --- |
| 日期 | 2026-09-09 |
| 套件版本 | traffickit 0.1.0 |
| OS | Windows 11 Pro 10.0.26200 |
| Python | 3.10.5 |
| 相依套件 | pandas 2.3.3、numpy 2.2.6 |
| 可編輯安裝與範例 | 成功；8 台車的兩張表與 summary 和手算一致 |
| 規格測試 | 本功能 23 個全部通過（當時全專案 47 個） |
| wheel 建置 | 成功產生 `dist/traffickit-0.1.0-py3-none-any.whl` |
| 另一個虛擬環境安裝 wheel | 成功（`.venv-check`）；再次通過範例與 47 個測試 |
| 效能 | 200,000 列通過紀錄／25 個轉向／3 個分組，約 0.38 秒（單次量測） |

## 舊程式差異與已知限制

`data/TurnVolumeAnalysis.vue` 是前端元件，計算在後端 `getTurnVolumeReport`
端點，**該端點的原始碼未取得**。因此下表是「與前端所呈現的行為」比對，
不是與後端算法逐行比對。

| 舊版行為（前端所見） | 本套件 | 差異說明 |
| --- | --- | --- |
| 後端回傳 `result[進入][轉向][分組] = {count, pcu}` | `by_turn` 長格式表 | 巢狀字典改成表格；資訊等價 |
| 前端用 `movements.some(...)` 判斷 `allowed_turns` | `by_turn.is_allowed`（取 any） | 判定規則相同，改由套件計算 |
| 只看得到轉向層級 | 多一張 `movements` 表保留 `exit_gate` | 五岔路口兩個出口都算右轉時可拆開看 |
| 未定義的 (from,to) 行為不明 | 拋 `ValueError` | 寧可擋下來，也不要靜靜算出一份少了車的報表 |
| 未分組車種默默不見 | 記入 `unassigned_*` | 分母說得清楚 |
| 違規轉向（`is_allowed=False` 卻有車）行為不明 | 照實計數並標記 | 這是真實資訊，不應被隱藏 |
| PCU 權重寫在前端 `DEFAULT_GROUPS` | 必填參數，另提供 `DEFAULT_PCU_WEIGHTS` 常數 | 權重是案件設定，不是演算法的一部分 |
| 百分比、小計、總計在前端算 | 不提供 | 版面呈現；`groupby` 一行即可 |
| CSV 匯出 | 不提供 | 應用端責任 |

已知限制：

- **尚未與後端舊版計算逐項比對**，也尚未做真實資料回歸；接回舊系統前必須補。
  需要的東西：後端 turn volume analyser 的原始碼，或同一份資料的新舊輸出。
- 不支援同一台車多次通過（需要不同 `vehicle_id`）。
- 不支援時段切分、不支援 `turn` 四類以外的自訂類別（要加須升契約版）。
- 不做進出閘門判定、不做百分比、不做 CSV。
