# CLAUDE.md

給 AI 助理的專案慣例。使用者只要提供「需求說明」或「一份現成程式碼」，就依本文件完成擴充。

## 這個專案是什麼

TrafficKit（`traffickit`）是交通分析**計算**套件。只放會改變交通結果意義的邏輯；
資料讀取、單位換算來源、UI、HTTP、檔案輸出一律不進套件。

- 開發教學與交付格式：`docs/feature-development-guide.md`（Step 1–8）
- 功能索引與狀態定義：`docs/catalog.md`
- 各功能工作單：`docs/worksheets/<功能 ID>.md`
- 現成範本（做得最完整的一個功能）：`speed.speed_distribution`，
  對照 `src/traffickit/speed/_distribution.py`、`tests/test_speed_distribution.py`、
  `docs/worksheets/speed.speed_distribution.md`

分層：

| 子套件 | 責任 | 可以讀檔？ |
| --- | --- | --- |
| `traffickit.speed`、`traffickit.volume` | 交通計算 | 否 |
| `traffickit.formats` | 外部檔案 → 套件契約的表格 | 是，但只做欄位與型別轉換 |
| `traffickit._validation` | 兩個以上功能共用的輸入驗證 | 否 |

常用輸入格式：**MOTC_SU** 空拍影像軌跡 CSV（`*_CSV_SU.csv`），
讀取器與完整格式定義見 `docs/worksheets/formats.motc_su.md`。
路口代號順時針 A/B/C/D、進入結尾 I、離開結尾 O、X 為不完整軌跡、
FPS 預設 9.99（= 29.97/3 實際速率，格式定義文件寫的是整數 10）、
車種 h（聯結車車頭）與 g（車身）是同一輛車的兩列。

## 收到擴充需求時的固定流程

1. 讀 `docs/catalog.md`，確認要新增的功能與既有功能是否重疊、能否只加參數解決。
2. 寫出 I/O 契約與**三個手算案例**（成立／不成立／邊界），先與使用者確認再寫程式。
3. 依下列清單交付，**八項缺一不可**（也可以直接用 `new-traffic-feature` skill）：

| # | 產出 | 位置 |
| --- | --- | --- |
| 1 | 實作 | `src/traffickit/<領域>/_<功能>.py` |
| 2 | 公開匯出 | `src/traffickit/<領域>/__init__.py` 的 `__all__` |
| 3 | 可執行範例 | `examples/<功能>_demo.py` |
| 4 | 規格測試 | `tests/test_<功能>.py` |
| 5 | 目錄登記 | `docs/catalog.md` 新增一列 |
| 6 | 工作單 | `docs/worksheets/<功能 ID>.md`，並加進 `docs/worksheets/index.md` 的 toctree |
| 7 | **API reference** | `docs/api/<子套件>.rst` 的 `autosummary` 加上名稱 |
| 8 | 驗證紀錄 | 工作單的「驗證環境與版本」表，填實際跑出來的結果 |

第 7 項容易漏。API reference 的**內容**由 docstring 產生，但名稱沒加進
`autosummary` 清單就不會出現在網站上——寫 docstring 與登記名稱是兩件事。
新增子套件時另外建一頁並加進 `docs/api/index.rst` 的 toctree 與分層表格。

4. 執行驗證（見下方指令），把實際數字填進工作單，再回報。

## 程式碼慣例

- **單位**：速度 m/s、時間為「相對本資料集共同起點的秒數」、長度公尺。
  函式參數與欄位名一律帶單位後綴（`_mps`、`_s`、`_m`）。
- **輸入契約**：`pandas.DataFrame`，必要欄位 `vehicle_id`（非空白字串）、`time_s`、
  `speed_smooth_mps`。允許未排序、允許多餘欄位、列索引可重複。
  沿用 `_distribution.py` 的 `_validated_samples()` 驗證邏輯與錯誤訊息措辭。
- **錯誤政策**：型別錯 → `TypeError`；欄位／數值／參數不符 → `ValueError`，
  訊息用繁體中文並指出欄位或參數名稱。**不默默排除無效列**；若某功能真的要排除，
  必須同時回報排除數量與原因，並寫進工作單。
- **不修改輸入**：一律 `tracks.loc[:, list(_REQUIRED)].copy()` 後再處理。
- **不做 I/O**：計算功能（`traffickit.speed`、`traffickit.volume`）不讀寫檔案、
  不連資料庫、不 print。**唯一例外是 `traffickit.formats` 格式轉換層**：
  它可以讀檔，但只做欄位與型別轉換，不做任何交通判定（不推轉向、不算速度、
  不裁時段、不排除任何資料列）。新的輸入格式一律放這一層，不要塞進計算功能。
- **公開介面**：實作放底線開頭的模組，經 `__init__.py` 匯出；
  呼叫端只寫 `from traffickit.<領域> import <函式>`。
- **參數**：關鍵參數用 keyword-only（`*` 之後）。**不給預設門檻或預設分箱**——
  忘記設定時應該報錯，而不是套用一個看起來正常的錯數字。
- **輸出**：固定欄位與固定 dtype，空結果也要保持同一個 schema。
  數值型統計量在未定義時回 `None`，不要用 `0.0` 代替（例如單車的樣本標準差）。
- **回傳型別**：單一表格用 DataFrame；需要同時回傳表格與分母／統計量時，
  用 `@dataclass(frozen=True)`（參考 `SpeedDistribution`）。
- **docstring**：NumPy 格式，繁體中文，必含 Parameters／Returns／Raises／Notes；
  Notes 要寫明「本功能不做什麼」。
- **註解**：只寫「為什麼」，不重述程式碼。全檔案繁體中文。

## 測試慣例

- 用內建 `unittest`，不引入 pytest。
- 測試要驗證**契約與交通定義**，不可把算法重寫一遍當預期答案。
- 每個功能至少涵蓋：手算答案、每個參數選項、邊界值（含門檻相等）、空輸入、
  全數被過濾、未排序＋重複索引＋不修改輸入、缺欄位、無效數值、無效參數。
- 手算的期望值用分數形式寫出（例如 `32 / 3`）並在註解說明推導，方便人工核對。

## 驗證指令（Windows PowerShell，專案根目錄）

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[docs]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe examples\<功能>_demo.py
.\.venv\Scripts\python.exe -m sphinx -b html -W --keep-going -d docs\_build\doctrees docs docs\_build\html
```

文件建置用 `-W`（警告即失敗），會抓出 docstring 語法錯誤、toctree 漏頁、
交叉參照失效。**繁體中文 docstring 的 RST 陷阱**：行內標記的結束符後面不能
直接接中文字或全形開括號，例如 ``**嚴格大於**門檻`` 與 ``` ``None``（說明） ```
都會報錯；改成結束符後接 `。`、`，`、`：` 或半形空白。

交付前的完整驗收（wheel + 乾淨環境）：

```powershell
.\.venv\Scripts\python.exe -m pip wheel --no-deps . --wheel-dir dist
python -m venv .venv-check
.\.venv-check\Scripts\python.exe -m pip install dist\traffickit-0.1.0-py3-none-any.whl
.\.venv-check\Scripts\python.exe examples\<功能>_demo.py
.\.venv-check\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-check\Scripts\python.exe -m pip freeze > requirements-validated.txt
```

註：`.venv-check` 若已存在需先刪除重建，否則會沿用舊版套件。

## 資訊不足時，一定要先問使用者

不要自行假設下列事項，這些會直接改變交通結果的意義：

1. **統計對象與分母**：每車一筆還是每樣本一筆？不符合條件的對象要不要保留在分母？
2. **邊界比較**：用 `>` 還是 `>=`？區間左閉右開還是兩端都含？
3. **同值時選誰**：取最早時間、取最大值，還是全部回傳？
4. **時間範圍**：先切時段再計算，還是先計算再篩選？兩者答案不同。
5. **前置條件**：輸入是否已平滑／已換算單位／已切 ROI？誰負責？
6. **無效資料**：缺值、負值、離群值要拋錯還是排除？排除的話怎麼回報？
7. **負責人**：新功能在 `docs/catalog.md` 的「負責人」欄要填誰。**每次都問，不要沿用。**
8. **路口幾何與管制**：分支是否順時針編號、哪些轉向合法（尤其迴轉）、
   分支是否等角分布。`clockwise_movements` 只推導幾何，不知道現場管制。

問題要具體到「兩個選項各會得到什麼答案」，不要問「你想怎麼做」。
一次把問題問完，不要來回擠牙膏。

## 從舊程式移植時

`data/` 放的是舊版參考程式（例如 `speed_analyser.py`），**不參與建置**。移植時：

- 逐項列出新舊差異，寫進 `docs/catalog.md` 的對照表，並向使用者確認每一項是預期的。
- 舊程式裡的 UI 預設值、客戶路徑、比例尺讀取、流向欄位名稱差異，都留在應用端。
- **「與舊版輸出相同」不等於交通定義正確。** 舊版的可疑行為（例如把未定義的統計量填 0、
  把範圍外的資料從分母中消掉）要指出來，不要照抄。
- 真實資料回歸比較需要使用者提供資料，做不到就在工作單註明「尚未回歸比較」。

## 不要做的事

- 不要為了通過測試而放寬契約；契約要改就先跟使用者確認，並在 catalog 升「契約版」。
- 不要新增相依套件（目前只有 pandas、numpy）；需要時先問。
- 不要動 `data/` 裡的舊程式。
- 不要在功能還沒做真實資料回歸比較前，把 catalog 狀態寫成「正式」。
- 不要只改程式不改 docstring——API reference 完全由 docstring 產生，
  改了程式沒改 docstring，網站上就是錯的。
