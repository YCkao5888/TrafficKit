# 工作單：formats.motc_su

依 [`feature-development-guide.md`](../feature-development-guide.md)
「每個新功能都要填的一張工作單」填寫。

- **功能 ID**：formats.motc_su
- **一句目的**：把 MOTC_SU 空拍影像軌跡 CSV 讀成套件契約的表格。
- **主要負責人**：yckao
- **公開函式入口**：`traffickit.formats.read_motc_su_passages`、
  `traffickit.formats.read_motc_su_tracks`
- **契約版**：1
- **狀態**：試行
- **參考來源**：`空拍影像分析_輸出資料相關定義_v1.1.xlsx` 的
  「軌跡檔_Pixel Frame」分頁（權威定義）；
  範例檔 `data/(YOLOv4_2504.1)桃園市八德區廣福路_福國北街_福國街_1A架次_CSV_SU.csv`

> **這一層為什麼可以讀檔？** `traffickit.formats` 是格式轉換層，只做欄位與
> 型別轉換，不做任何交通判定。計算功能（`traffickit.speed`、
> `traffickit.volume`）仍維持零 I/O，可以直接接後端、資料庫或測試資料。

## 格式定義

CSV，**無標題列，每列長度不一**。一列一台車：

```
車輛ID, 進入路口frame, 離開路口frame, 進入代號, 離開代號, 車種, x1,y1,x2,y2,x3,y3,x4,y4, (下一個 frame 的八個值)...
```

| 位置 | 內容 | 規則 |
| --- | --- | --- |
| 1 | 車輛 ID | 非空白；檔案內不可重複 |
| 2 | 進入路口 frame | 非負整數 |
| 3 | 離開路口 frame | 非負整數，且不小於進入 frame |
| 4 | 進入路口代號 | `[A-Z]+I`（例如 `AI`）或 `X` |
| 5 | 離開路口代號 | `[A-Z]+O`（例如 `AO`）或 `X` |
| 6 | 車種代號 | p 行人、u 自行車、m 機車、c 汽車、t 貨車、b 巴士、h 聯結車車頭、g 聯結車車身 |
| 7… | 軌跡座標 | 每 8 個值一個 frame：四角點 (x1,y1)…(x4,y4)，第一點為車頭左上，順時針 |

- **路口代號順時針編號**：從左側路口起為 A，依序 B、C、D。進入結尾 `I`、
  離開結尾 `O`。`X` 代表不完整軌跡，官方定義是「請忽略」。
- **座標單位是像素**，原點在影像左上、Y 軸向下。
- **FPS 預設 9.99**（= 29.97/3，NTSC 推導的實際拍攝速率）。
  格式定義文件寫的是整數 10，兩者不同時以實際速率為準；拍攝設定不同時要明確傳入 `fps`。
- **不變式**：軌跡值數量 = `8 × (離開frame − 進入frame + 1)`。
  本讀取器一律檢查這個等式，用來擋住錯位或截斷的檔案。

## 參數

| 參數 | 型別 | 預設 | 意義 |
| --- | --- | --- | --- |
| `path` | str / path-like | 無（必填） | CSV 檔路徑 |
| `fps` | float | `9.99` | 影像張數／秒，有限且大於 0。只影響 `time_s`，不影響 frame |
| `encoding` | str | `"utf-8"` | 檔案編碼 |

`fps` 是**唯一有預設值的參數**，因為它來自格式本身而不是本套件的判斷：
9.99 是 29.97/3 的實際拍攝速率。格式定義文件寫的是整數 10，
差異約 0.1%，換算成秒時每 1000 frame 差約 0.1 秒——短時距分析看不出來，
但整份 21 分鐘的影片累積約 1.3 秒。拍攝設定不同時務必傳入正確值。

## 輸出

### `read_motc_su_passages` → DataFrame（一列一台車）

依 `entry_frame`、`vehicle_id` 排序。

| 欄位 | 型別 | 意義 |
| --- | --- | --- |
| `vehicle_id` | string | 車輛 ID |
| `entry_gate` / `exit_gate` | string | 路口代號，**已去掉結尾 I／O**；不完整者為 `X` |
| `vehicle_class` | string | 車種代號 |
| `entry_frame` / `exit_frame` | int64 | 進入／離開 frame |
| `frame_count` | int64 | `exit_frame - entry_frame + 1` |
| `entry_time_s` / `exit_time_s` | float64 | `frame / fps` |
| `is_complete` | bool | 進出代號都不是 `X` |

軌跡座標不會讀進記憶體，只驗證數量。

### `read_motc_su_tracks` → DataFrame（一列一台車一個 frame）

依 `vehicle_id`、`frame` 排序。欄位：`vehicle_id`、`frame`、`time_s`、
`x1_px`…`y4_px`、`center_x_px`、`center_y_px`（四角點平均）、`is_complete`。

## 判定規則

1. 逐行剖析，空白行跳過；任何不符格式的行拋 `ValueError`，**訊息含行號**。
2. 路口代號去掉結尾 I／O；`X` 原樣保留並把 `is_complete` 設為 False。
3. `time_s = frame / fps`。frame 0 即時間原點。
4. 驗證軌跡值數量等於 `8 × frame 數`。
5. 車輛 ID 重複 → 拋錯（下游的轉向流量契約要求 ID 唯一）。

## 前置條件

無。這是最上游的讀取層。

## 品質政策

| 情況 | 本功能行為 |
| --- | --- |
| 欄位不足 6 個、ID 空白、frame 非整數／負數／倒置 | 拋 `ValueError`，含行號 |
| 路口代號不符 `[A-Z]+I` / `[A-Z]+O` 也不是 `X` | 拋 `ValueError`，含行號 |
| 車種代號不在格式定義的八個之內 | 拋 `ValueError`，含行號 |
| 軌跡值數量與 frame 數不符 | 拋 `ValueError`，含行號與兩個數字 |
| 軌跡座標含非數值 | `read_motc_su_tracks` 拋 `ValueError`（passages 不解析座標） |
| 車輛 ID 重複 | 拋 `ValueError`，列出前 5 個 |
| **不完整軌跡（`X`）** | **照樣讀入並標記 `is_complete=False`，不默默丟掉** |
| 空檔案 | 回傳固定欄位與型別的空表 |
| 檔案不存在 | 拋 `FileNotFoundError` |

不完整軌跡不自動排除，是刻意的：官方說「請忽略」是**分析上的建議**，
不是讀取器該替呼叫端做的決定。呼叫端寫 `.query("is_complete")` 一行即可，
而且過濾掉幾台是看得見的。

## 統計口徑

本功能不做統計。`read_motc_su_passages` 的列數 = 檔案中的車輛數（含不完整）。

## 手算範例

三列的示範檔（見 `tests/test_motc_su.py` 的 `SAMPLE`）：

| 列 | 內容 | 預期 passages |
| --- | --- | --- |
| 1 | `1,0,1,BI,AO,c,` + 兩個 frame 的八個座標 | B→A、汽車、frame 0–1、frame_count 2、0 至 1/9.99 ≈ 0.1001 秒、完整 |
| 2 | `2,2,2,AI,CO,m,` + 一個 frame | A→C、機車、frame 2、frame_count 1、2/9.99 ≈ 0.2002 秒、完整 |
| 3 | `3,2,2,X,CO,c,` + 一個 frame | entry_gate `X`、**`is_complete=False`** |

`read_motc_su_tracks` 對同一份檔案回傳 2+1+1 = 4 列；
第一列的四角點 (0,0)(10,0)(10,10)(0,10) → 中心點 (5.0, 5.0)。

**邊界案例**：宣告 frame 0–1 卻只給一個 frame 的座標 →
`ValueError：第 1 行有 8 個軌跡值，但 frame 數 2 應對應 16 個`。

## 原始碼／範例／測試位置

- 原始碼：`src/traffickit/formats/_motc_su.py`
- 範例：`examples/motc_su_turn_volume_demo.py`（讀檔 → 轉向對照表 → 轉向流量）
- 測試：`tests/test_motc_su.py`（28 個測試，含格式、轉向對照表與端到端）

## 驗證環境與版本

| 項目 | 內容 |
| --- | --- |
| 日期 | 2026-09-09 |
| 套件版本 | traffickit 0.1.0 |
| OS | Windows 11 Pro 10.0.26200 |
| Python | 3.10.5 |
| 相依套件 | pandas 2.3.3、numpy 2.2.6 |
| 真實檔案 | `(YOLOv4_2504.1)桃園市八德區廣福路_福國北街_福國街_1A架次_CSV_SU.csv`，27.8 MB |
| 讀取結果 | 2,179 台車；不完整（X）179 台；進出代號 A–D；車種 b/c/m/t；frame 2–12678（約 21.2 分鐘 @9.99fps） |
| 不變式檢查 | 2,179 列全部符合「軌跡值數 = 8 × frame 數」 |
| 規格測試 | 本功能 28 個；全專案 75 個全部通過 |
| wheel 建置與乾淨環境安裝 | 成功；範例與 75 個測試再次通過 |
| 效能 | `read_motc_su_passages` 2,179 列約 0.08 秒；`read_motc_su_tracks` 822,185 列約 1.5 秒、約 130 MB 記憶體 |

## 舊程式差異與已知限制

本功能沒有對應的舊程式，是新寫的讀取層。與格式定義文件的差異：

| 定義文件 | 本讀取器 | 理由 |
| --- | --- | --- |
| 「X 為不完整軌跡請忽略」 | 讀入並標記 `is_complete=False` | 忽略是分析決定，不是讀取決定；過濾掉幾台要看得見 |
| 未規定讀取器要不要驗證資料 | 一律驗證並拋錯（含行號） | 錯位或截斷的檔案應該擋下來 |
| 代號含 I／O 後綴 | 輸出去掉後綴 | 後綴只是進出方向標記，去掉後才能與 `movements` 的路口代號對齊 |

已知限制：

- **h（車頭）與 g（車身）是同一輛聯結車的兩列，本讀取器不合併**，
  因為檔案沒有提供兩者的關聯。做車輛數統計時把 `g` 留在車種分組之外，
  它會出現在 `summary.unassigned_classes` 而不會被默默計入。
  本次真實檔案沒有 h／g，此路徑**尚未用真實資料驗證**。
- 只支援 Pixel Frame 版；同一份定義文件的 SSAM 版格式不同，尚未支援。
- `read_motc_su_tracks` 一次載入全部座標，超大檔案需要分批時要另外設計。
- 不做座標單位換算、不做速度計算、不判定轉向。
