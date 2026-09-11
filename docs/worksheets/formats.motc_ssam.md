# 工作單：formats.motc_ssam

依 [`feature-development-guide.md`](../feature-development-guide.md)
「每個新功能都要填的一張工作單」填寫。

- **功能 ID**：formats.motc_ssam
- **一句目的**：把 MOTC 空拍影像軌跡檔的 SSAM 版讀成套件契約的表格。
- **主要負責人**：yckao
- **公開函式入口**：`traffickit.formats.read_motc_ssam_vehicles`、
  `traffickit.formats.read_motc_ssam_tracks`
- **契約版**：1
- **狀態**：試行
- **參考來源**：`空拍影像分析_輸出資料相關定義_v1.1.xlsx` 的「軌跡檔_SSAM」分頁
  （該分頁只寫路口代號與車種代號，欄位定義轉引 SSAM tutorial）；
  舊程式 `video_add_veh_bbox.py` 的 `load_ssam_csv`（本機參考，未納入版控）；
  一份真實的 `*_CSV_SSAM.csv`（本機參考，未納入版控；
  依慣例不在文件中記錄真實案件的檔名或路口名稱）

> **這一層為什麼可以讀檔？** `traffickit.formats` 是格式轉換層，只做欄位與
> 型別轉換，不做任何交通判定。計算功能（`traffickit.speed`、
> `traffickit.volume`）仍維持零 I/O。

## 與 Pixel Frame 版的關係

同一批分析成果的兩種輸出，**不是兩種不同的資料**：

| | Pixel Frame 版（`formats.motc_su`） | SSAM 版（本功能） |
| --- | --- | --- |
| 粒度 | 一列一台車，軌跡接在同一列 | 一列一台車一個時間步 |
| 座標 | 像素 | 公尺 |
| 時間 | frame 編號 | `Timestep`，秒 |
| 車身 | 四個角點 | 車頭中點、車尾中點、車長、車寬 |
| 路口代號 | A/B/C/D＋I/O，X 為不完整 | **完全相同** |
| 車種代號 | p/u/m/c/t/b/h/g | **完全相同** |
| 標題列 | 無 | 有，前面還有 FORMAT／DIMENSIONS 區塊 |

因為代號共用，兩版的 `*_vehicles` 輸出都能直接餵給 `summarise_turn_volume`。
共用的代號剖析放在 `src/traffickit/formats/_motc_common.py`。

## 格式定義

檔案開頭是 FORMAT／DIMENSIONS 區塊，接著是標題列，之後才是資料：

```
FORMAT,,,,,,,,,,,,,,
 ,Byte Order,L,,,,,,,,,,,,
 ,Version,1.04,,,,,,,,,,,,
DIMENSIONS,,,,,,,,,,,,,,
 ,Units,1,,,,,,,,,,,,
 ,Scale,1,,,,,,,,,,,,
Timestep,Vehicle ID,Link ID,Lane ID,Front X,Front Y,Rear X,Rear Y,Length,Width,Speed,Acceleration,intersection in,intersection out,class
0.1001001,,,,,,,,,,,,,,
0.1001001,1,1,1,87.819,55.2979,82.6862,55.2177,5.1253,2.3800,8.02,-0.1,AI,BO,c
```

- **DIMENSIONS 區塊的 `Scale`、`MaxX` 等值是佔位值**，與真實比例無關
  （實測 `MaxX,100` 但資料中有 125 的座標）。不要拿它當比例尺。
- **每個時間步前有一列只有 `Timestep` 的分隔列。** 有兩種寫法：只有一個
  欄位，或把逗號補滿到與標題列同寬。本讀取器以「除了第一欄以外都是空的」
  判斷，兩種都略過。
- **標題列的欄位順序不固定**，且與 SSAM tutorial 的欄位清單不完全相同
  （實測檔多了 `Acceleration`，且 `class` 排在最後）。本讀取器**以欄位名稱
  定位**，比對時去空白並轉小寫，不依賴位置。

必要欄位（缺任一個就拋錯）：

| 標題列名稱 | 輸出欄位 | 意義 |
| --- | --- | --- |
| `Timestep` | `time_s` | 秒 |
| `Vehicle ID` | `vehicle_id` | 車輛 ID |
| `Front X` / `Front Y` | `front_x_m` / `front_y_m` | 車頭中點（公尺） |
| `Rear X` / `Rear Y` | `rear_x_m` / `rear_y_m` | 車尾中點（公尺） |
| `Length` | `length_m` | 宣告車長（公尺） |
| `Width` | `width_m` | 車寬（公尺） |
| `class` | `vehicle_class` | 車種代號 |
| `intersection in` / `intersection out` | `entry_gate` / `exit_gate` | 路口代號 |

`Link ID`、`Lane ID`、`Speed`、`Acceleration` 目前不讀，見「已知限制」。

### 時間基準

`Timestep` 是秒。實測**每個值乘以 9.99 都是整數**（最大偏差 5e-7），
與 Pixel Frame 版的 `DEFAULT_FPS = 9.99` 完全一致——這是兩份來自不同架次的
檔案各自得到的結果，互相佐證了 9.99（= 29.97/3）就是實際拍攝速率。

**但這不表示兩版的時間原點對齊。** 手上兩份檔是不同架次，無法驗證同一架次
的 SSAM `Timestep × fps` 是否等於 Pixel Frame 版的 frame 編號。兩版要合用時
請自行校正，或提供同一架次的兩個檔補做驗證。

### 行穿線代號

格式定義文件的 SSAM_TTC_PET 分頁寫「車輛範例為 AI、BI，不完整軌跡為 X，
**行人則是 AB、BC**」。也就是行人走行穿線時，代號是**兩個路口字母**、
沒有 I／O 後綴。

實測完全吻合：1275 台車中有 398 台使用行穿線代號（AB／BC／CD／DA），
正好是全部 386 個行人加 12 台自行車，**沒有任何一台汽機車使用這種代號**。

本讀取器接受這種代號、原樣保留，並標記 `is_crosswalk=True`。
`formats.motc_su` 同步放寬（見該功能契約版 2）。

## 參數

| 參數 | 型別 | 預設 | 意義 |
| --- | --- | --- | --- |
| `path` | str / path-like | 無（必填） | CSV 檔路徑 |
| `encoding` | str | `"utf-8-sig"` | 檔案編碼。有沒有 BOM 都讀得到 |

**沒有比例尺參數，也沒有 fps 參數。** 座標原本就是公尺、時間原本就是秒，
本層不做任何換算。要畫到影像上才需要比例尺，那屬於呼叫端。

## 輸出

### `read_motc_ssam_vehicles` → DataFrame（一列一台車）

依 `entry_time_s`、`vehicle_id` 排序。

| 欄位 | 型別 | 意義 |
| --- | --- | --- |
| `vehicle_id` | string | 車輛 ID |
| `entry_gate` / `exit_gate` | string | 路口代號，**已去掉結尾 I／O**；不完整者為 `X`；行穿線代號原樣保留 |
| `vehicle_class` | string | 車種代號 |
| `entry_time_s` / `exit_time_s` | float64 | 該車最早／最晚出現的 `Timestep` |
| `sample_count` | int64 | 該車在檔案中的列數 |
| `is_complete` | bool | 進出代號都不是 `X` |
| `is_crosswalk` | bool | 進入或駛出代號是行穿線代號 |

與 `read_motc_su_vehicles` 的差別只有一處：**SSAM 版沒有 frame 編號**，
因此沒有 `entry_frame`／`exit_frame`／`frame_count`，改以 `sample_count`
表示取樣列數。

### `read_motc_ssam_tracks` → DataFrame（一列一台車一個時間步）

依 `vehicle_id`、`time_s` 排序。欄位：`vehicle_id`、`time_s`、
`front_x_m`、`front_y_m`、`rear_x_m`、`rear_y_m`、`length_m`、`width_m`、
`x1_m`…`y4_m`、`center_x_m`、`center_y_m`、`is_complete`、`is_crosswalk`。

四個角點由車頭中點、車尾中點與車寬**幾何還原**：車身方向的單位向量取
`(front − rear) / |front − rear|`，垂直方向取其法向量，往兩側各展開半個車寬。
繞行順序刻意對齊 Pixel Frame 版：`x1`／`x2` 是車頭兩角、`x3`／`x4` 是車尾兩角。

## 判定規則

1. 逐列剖析。找到第一欄是 `Timestep` 的列之前，全部略過。
2. 空白列與時間步分隔列略過；其餘欄位數不足的列拋 `ValueError`，**訊息含行號**。
3. 欄位以名稱定位（去空白、轉小寫），不依賴位置。
4. 路口代號去掉結尾 I／O；`X` 與行穿線代號原樣保留並設對應旗標。
5. 同一個 `vehicle_id` 的進出代號與車種必須全檔一致，不一致拋錯並指出兩個行號。
6. 同一個 `vehicle_id` 不可在同一個 `Timestep` 出現兩次。

## 前置條件

無。這是最上游的讀取層。

## 品質政策

| 情況 | 本功能行為 |
| --- | --- |
| 找不到 `Timestep` 標題列 | 拋 `ValueError` |
| 標題列缺必要欄位 | 拋 `ValueError`，列出缺哪些、實際有哪些 |
| 欄位數不足且不是分隔列 | 拋 `ValueError`，含行號 |
| 數值欄位不是數值，或是 inf／nan | 拋 `ValueError`，含行號與欄位名 |
| 車輛 ID 空白 | 拋 `ValueError`，含行號 |
| 路口代號不符格式 | 拋 `ValueError`，含行號 |
| 車種代號不在格式定義的八個之內 | 拋 `ValueError`，含行號 |
| 車寬不是正數 | 拋 `ValueError`，含行號 |
| **車頭與車尾座標相同** | 拋 `ValueError`，含行號 |
| 同一台車的代號或車種前後不一致 | 拋 `ValueError`，含兩個行號 |
| 同一台車在同一時間步重複出現 | 拋 `ValueError`，含行號 |
| **不完整軌跡（`X`）** | **照樣讀入並標記 `is_complete=False`** |
| **行穿線代號（`AB`）** | **照樣讀入並標記 `is_crosswalk=True`** |
| 只有標題列、沒有資料 | 回傳固定欄位與型別的空表 |
| 檔案不存在 | 拋 `FileNotFoundError` |

「車頭與車尾座標相同」之所以拋錯而不是略過：這種列算不出車身方向，還原出
的角點會是任意方向，畫出來或拿去算角度都是錯的，而且錯得不明顯。實測的
真實檔沒有這種列；若之後遇到（例如車長為 0 的行人），再依實際情況調整，
不要先放寬。

## 統計口徑

本功能不做統計。`read_motc_ssam_vehicles` 的列數 = 檔案中的車輛數
（含不完整與行穿線）。`sample_count` 的總和 = `read_motc_ssam_tracks` 的列數。

## 手算範例

四台車的示範檔（見 `tests/test_motc_ssam.py` 的 `SAMPLE`）：

| 車 | 內容 | 預期 vehicles |
| --- | --- | --- |
| 1 | 兩個時間步，`BI`→`AO`，汽車 | B→A、entry 0.1、exit 0.2、sample_count 2、完整 |
| 2 | 一個時間步，`AI`→`CO`，機車 | A→C、sample_count 1、完整 |
| 3 | 一個時間步，`AB`→`AB`，行人 | 代號原樣保留、**`is_crosswalk=True`**、`is_complete=True` |
| 4 | 一個時間步，`X`→`CO`，汽車 | entry_gate `X`、**`is_complete=False`** |

**角點還原手算**：車 1 在 0.1 秒，車頭中點 (10, 5)、車尾中點 (6, 5)、車寬 2。
車身方向 (1, 0)，法向量 (0, −1)，半寬 1 →
車頭兩角 (10, 4)、(10, 6)；車尾兩角 (6, 6)、(6, 4)。
中心點 (8, 5)，同時等於四角點平均與車頭車尾中點的中點。

**邊界案例**：車頭與車尾座標相同 →
`ValueError：第 4 行的車頭與車尾座標相同，無法決定車身方向`。

## 原始碼／範例／測試位置

- 原始碼：`src/traffickit/formats/_motc_ssam.py`
  （共用代號剖析在 `src/traffickit/formats/_motc_common.py`）
- 範例：`examples/motc_ssam_demo.py`（讀檔 → 公尺位移 → 轉向流量）
- 測試：`tests/test_motc_ssam.py`（33 個測試，含格式、品質政策與端到端）

## 驗證環境與版本

| 項目 | 內容 |
| --- | --- |
| 日期 | 2026-09-11 |
| 套件版本 | traffickit 0.1.0 |
| OS | Windows 11 Pro 10.0.26200 |
| Python | 3.10.5 |
| 相依套件 | pandas 2.3.3、numpy 2.2.6 |
| 真實檔案 | 本機一份 `*_CSV_SSAM.csv`，20.8 MB，四岔路口單一架次 |
| 讀取結果 | 1,275 台車；不完整（X）305 台；行穿線 398 台；進出代號 A–D／AB／BC／CD／DA／X；車種 m 535、p 386、c 304、t 31、u 12、b 6、g 1 |
| 時間範圍 | 0.1001 ~ 308.7087 秒（約 5.1 分鐘） |
| 時間基準檢查 | 全部 `Timestep × 9.99` 與整數的最大偏差 5e-7 |
| 轉向流量 | 過濾 X 與行穿線後 571 台，總 PCU 397.97 |
| 規格測試 | 本功能 33 個全部通過（當時全專案 117 個） |
| 效能 | `read_motc_ssam_vehicles` 1,275 台約 1.5 秒；`read_motc_ssam_tracks` 224,166 列約 3.1 秒、常駐約 44 MB（另一次開啟 tracemalloc 追蹤時測得峰值約 240 MB，該次耗時 9.4 秒） |

## 舊程式差異與已知限制

舊程式是本機的 `video_add_veh_bbox.py`（在空拍影片上畫 bbox 的工具），
其 `load_ssam_csv` 讀同一種檔案。差異：

| 舊程式 | 本讀取器 | 理由 |
| --- | --- | --- |
| 必須傳入比例尺，讀完就把公尺換成像素 | 不接受比例尺，輸出公尺 | 公尺是檔案的原生單位，也是本套件的單位慣例；換像素是繪圖需求 |
| `intersection in/out`、`class` 是選填，沒有就留空 | 必要欄位，缺了拋錯 | 缺這些就算不出轉向流量，早點擋下來 |
| 無法解析的列靜默跳過 | 拋錯並指出行號 | 不默默排除無效列 |
| 同一車同一時間步重複取樣時保留第一筆 | 拋錯 | 重複代表資料有問題，不該由讀取器替呼叫端選 |
| 依 `Timestep × fps` 換算成影格編號 | 保留原始秒數 | frame 編號是影片的概念，不是這份資料的 |
| 會修正車頭／車尾角點被對調的影格 | 不做 | SSAM 版的車頭車尾是分開的欄位，不會對調；這是 Pixel Frame 版才有的問題 |

已知限制：

- **`Speed` 與 `Acceleration` 欄位不讀。** 實測 `Speed` 的單位是公尺／秒
  （用相鄰時間步的位移比對，18,987 個樣本的中位數比值 1.03；若是 km/h
  應為 0.28），但這是量出來的，格式定義文件沒有寫明，因此暫不納入契約。
  要納入前請先向產製端確認。
- **`length_m` 不等於車頭中點到車尾中點的距離。** 實測 224,166 列中有
  6,838 列（3.0%）相差超過 0.5 公尺，最大差 13.6 公尺，出現在聯結車車身
  （`g`，宣告車長 16.4 公尺但車頭車尾只隔 2.8 公尺）。還原角點用的是
  車頭車尾座標，不是這個欄位；兩個都給，由呼叫端決定要量哪一個。
- **Y 軸朝向未確認。** 角點的繞行順序是照舊程式對齊 Pixel Frame 版寫的，
  但「哪一角是左」取決於座標系 Y 軸方向，格式定義文件沒寫。要在影像上疊圖
  之前應先用真實影片核對一次。
- **與 Pixel Frame 版的時間原點是否對齊，尚未驗證**（手上兩份檔是不同架次）。
- 實測檔出現 1 台車種 `g`（聯結車車身）卻沒有對應的 `h`（車頭）。與
  Pixel Frame 版一樣，本讀取器不合併這兩者，統計時把 `g` 留在車種分組之外。
- 不做座標單位換算、不做速度計算、不判定轉向、不內插取樣點之間的位置。
- `read_motc_ssam_tracks` 一次載入全部列，超大檔案需要分批時要另外設計。
