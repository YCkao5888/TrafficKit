# CLAUDE.md

給 AI 助理的專案慣例。使用者只要提供「需求說明」或「一份現成程式碼」，就依本文件完成擴充。

## 這個專案是什麼

TrafficKit（`traffickit`）是交通分析**計算**套件。只放會改變交通結果意義的邏輯；
資料讀取、單位換算來源、UI、HTTP、檔案輸出一律不進套件。

- 開發教學與交付格式：`docs/feature-development-guide.md`（Step 1–8）
- 功能索引與狀態定義：`docs/catalog.md`
- 各功能工作單：`docs/worksheets/<功能 ID>.md`
- 發行與文件更新檢查表：`docs/release-checklist.md`
- 線上文件：<https://yckao5888.github.io/TrafficKit/latest/>
- **這個 repo 是公開的**（<https://github.com/YCkao5888/TrafficKit>）。
  推上去的任何東西全世界都看得到，提交前務必做下面的機敏性檢查。
  （Sphinx 產生，原始碼就是 `docs/`；推 master 後由 GitHub Actions 自動更新）
- 現成範本（做得最完整的一個功能）：`speed.speed_distribution`，
  對照 `src/traffickit/speed/_distribution.py`、`tests/test_speed_distribution.py`、
  `docs/worksheets/speed.speed_distribution.md`

分層：

| 子套件 | 責任 | 可以讀檔？ |
| --- | --- | --- |
| `traffickit.speed`、`traffickit.volume` | 交通計算 | 否 |
| `traffickit.formats` | 外部檔案 → 套件契約的表格 | 是，但只做欄位與型別轉換 |
| `traffickit._validation` | 兩個以上功能共用的輸入驗證 | 否 |

**這個 repo 有兩個套件**（monorepo）：

| 路徑 | 套件名 | 相依 | 什麼進去 |
| --- | --- | --- | --- |
| `src/traffickit/` | `traffickit` | pandas、numpy | 會改變**數字**的邏輯 |
| `packages/traffickit-viz/` | `traffickit-viz` | traffickit、OpenCV | 會改變**畫面**的邏輯 |

**相依方向是單向的**：`traffickit_viz` 可以 import `traffickit`，
反過來永遠不行——核心一旦沾上 OpenCV，後端與 CI 就裝不動了。
`tests/test_layering.py` 專門守這條線，違反時所有功能測試仍會通過，
只有它會失敗。放哪一邊的判準：**改變數字的留核心，改變畫面的放 viz**。
`traffickit-viz` 詳見 `packages/traffickit-viz/README.md`。

常用輸入格式：**MOTC 空拍影像軌跡 CSV**，同一批分析成果有兩種輸出版本，
各有一份工作單：

| 版本 | 檔名 | 座標／時間 | 工作單 |
| --- | --- | --- | --- |
| Pixel Frame | `*_CSV_SU.csv` | 像素／frame 編號 | `docs/worksheets/formats.motc_su.md` |
| SSAM | `*_CSV_SSAM.csv` | 公尺／秒 | `docs/worksheets/formats.motc_ssam.md` |

兩版**共用**這些約定，定義放在 `src/traffickit/formats/_motc_common.py`：

- 路口代號順時針 A/B/C/D，進入結尾 I、離開結尾 O，X 為不完整軌跡。
- **行人與自行車走行穿線，代號是兩個路口字母**（`AB`、`BC`），沒有 I／O
  後綴。兩個讀取器都接受並標記 `is_crosswalk=True`；它跟 X 一樣不是路口
  代號，餵進轉向流量前要 `.query("is_complete and not is_crosswalk")`。
- 車種 p/u/m/c/t/b/h/g；h（聯結車車頭）與 g（車身）是同一輛車的兩列。
- 取樣率 9.99（= 29.97/3 實際速率，格式定義文件寫的是整數 10）。
  Pixel Frame 版由 `fps` 參數換算；SSAM 版的 `Timestep` 已經是秒，
  實測乘 9.99 為整數，兩版的取樣率一致。

**SSAM 版沒有比例尺參數**：座標原本就是公尺。檔案裡 DIMENSIONS 區塊的
`Scale` 是佔位值，不要拿來用。

## 收到擴充需求時的固定流程

1. 讀 `docs/catalog.md`，確認要新增的功能與既有功能是否重疊、能否只加參數解決。
2. 寫出 I/O 契約與**三個手算案例**（成立／不成立／邊界），先與使用者確認再寫程式。
3. 依下列清單交付，**九項缺一不可**（也可以直接用 `new-traffic-feature` skill）。
   **這張表是唯一來源**，skill 與 `docs/release-checklist.md` 都指回這裡；
   要改流程就改這張表，不要在別處另開一份。

| # | 產出 | 位置 |
| --- | --- | --- |
| 1 | 實作 | `src/traffickit/<領域>/_<功能>.py` |
| 2 | 公開匯出 | `src/traffickit/<領域>/__init__.py` 的 `__all__` |
| 3 | 可執行範例 | `examples/<功能>_demo.py` |
| 4 | 規格測試 | `tests/test_<功能>.py` |
| 5 | 目錄登記 | `docs/catalog.md` 新增一列＋一段功能說明 |
| 6 | 工作單 | `docs/worksheets/<功能 ID>.md`，並加進 `docs/worksheets/index.md` 的 toctree |
| 7 | **API reference** | `docs/api/<子套件>.rst` 的 `autosummary` 加上名稱 |
| 8 | **README** | 根目錄 `README.md` 的「功能索引」表；影響入門用法時一併更新開頭的「第一支腳本」或「快速上手」 |
| 9 | 驗證紀錄 | 工作單的「驗證環境與版本」表，填實際跑出來的結果 |

第 7、8 項最常漏。API reference 的**內容**由 docstring 產生，但名稱沒加進
`autosummary` 清單就不會出現在網站上——寫 docstring 與登記名稱是兩件事。
README 的功能索引是多數人第一眼看到的清單，漏掉等於新功能沒人知道。

**README 的 `python` 區塊由 `tests/test_readme_examples.py` 實際執行驗證**：
每個區塊都會被跑過，區塊後面若緊接一個沒有語言標記的 ``` 區塊，還會逐字比對
標準輸出。因此 README 的範例必須是**複製貼上就能跑**的完整程式（含 import 與
`print`），不可以留 `...`；要更新輸出時**實際跑一次再貼上**，不要用手改數字。
需要本機軌跡檔的範例會被跳過（以 `_CSV_SU.csv`、`_CSV_SSAM.csv` 判斷），
由 `examples/` 覆蓋。

4. 執行驗證（見下方指令），把實際數字填進工作單，再回報。

### 改了什麼 → 要更新哪些檔案

| 你改了什麼 | 除了程式與測試，還要更新 |
| --- | --- |
| 新增公開函式 | 上表九項全部 |
| 改既有函式的契約 | docstring、`catalog.md` 該列的契約版與「契約變更紀錄」、工作單、範例；若動到 README 的快速上手片段也要改 |
| 只改內部實作、效能或錯誤訊息措辭 | 只有程式與測試；契約版不動，文件不必改 |
| 新增子套件 | 九項＋`docs/api/<新>.rst`＋`docs/api/index.rst` 的 toctree 與分層表＋本檔的分層表＋README 專案結構 |
| 新增輸入格式 | 放 `traffickit.formats`，九項＋本檔「常用輸入格式」段 |
| 新增跨功能的共同約定 | 本檔「程式碼慣例」＋README「設計約定」＋`docs/index.md`「使用前必讀」（三處要一致） |
| 新增共用驗證函式 | `src/traffickit/_validation.py`，並確認既有呼叫端的錯誤訊息沒被改掉 |
| 新增視覺化／影片輸出功能 | 放 `packages/traffickit-viz`，**不要動核心**；該套件的 `__all__`、`README.md` 與 `tests/`，以及本檔的分層表 |
| 要發行一個版本 | 走 `docs/release-checklist.md`（版號、`docs/switcher.json`、tag） |

## 程式碼慣例

- **單位**：速度 m/s、時間為「相對本資料集共同起點的秒數」、長度公尺。
  函式參數與欄位名一律帶單位後綴（`_mps`、`_s`、`_m`）。
- **輸入契約**：一律 `pandas.DataFrame`，允許未排序、允許多餘欄位、列索引可重複。
  必要欄位由各功能自己訂，不是全套件共用一組：
  速度類用 `vehicle_id`／`time_s`／`speed_smooth_mps`（一列一台車一個時間點），
  轉向流量用 `vehicle_id`／`entry_gate`／`exit_gate`／`vehicle_class`（一列一台車）。
  驗證一律用 `src/traffickit/_validation.py` 的共用函式
  （`require_dataframe`、`require_columns`、`check_label_column`、
  `check_nonnegative_column`、`check_unique`、`check_real`），
  **沿用它們的錯誤訊息措辭**，不要另寫一套講法。
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

動到 `packages/traffickit-viz` 時另外跑（**先裝核心再裝它**，兩者都還沒上
PyPI，順序反了 pip 會去 PyPI 找 `traffickit` 而失敗）：

```powershell
.\.venv\Scripts\python.exe -m pip install -e packages/traffickit-viz
.\.venv\Scripts\python.exe -m unittest discover -s packages/traffickit-viz/tests -v
```

核心的 `unittest discover -s tests` **不會**跑到 viz 的測試，這是刻意的：
沒裝 OpenCV 的環境仍然要能跑完核心測試。CI 也分成兩個 job。

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
`requirements-validated.txt` 由最後那道 `pip freeze` 產生，記錄這次驗收實際
裝了哪些版本；跑完完整驗收就更新它並一起提交。它含本機 wheel 路徑，
**不是可搬移的部署鎖檔**。

**工作單裡的驗證紀錄是當下的快照。** 新增功能時只填自己那一份，
不必回頭改其他功能工作單裡的測試數量或日期——那些數字記錄的是「當時驗過什麼」，
不是「現在的總數」。

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

`data/` **已列入 `.gitignore`，整個目錄不在版控內、也不參與建置**，只存在於
開發者本機。裡面放三種東西：舊版參考程式（`speed_analyser.py`、
`TurnVolumeAnalysis.vue`、`video_add_veh_bbox.py`）、真實軌跡檔
（`*_CSV_SU.csv`、`*_CSV_SSAM.csv`）、以及客戶端的格式定義文件
（`空拍影像分析_輸出資料相關定義_v1.1.xlsx`）。
文件中引用這些檔名時，要註明是本機參考而非 repo 內的檔案。移植時：

- 逐項列出新舊差異，寫進 `docs/catalog.md` 的對照表，並向使用者確認每一項是預期的。
- 舊程式裡的 UI 預設值、客戶路徑、比例尺讀取、流向欄位名稱差異，都留在應用端。
- **「與舊版輸出相同」不等於交通定義正確。** 舊版的可疑行為（例如把未定義的統計量填 0、
  把範圍外的資料從分母中消掉）要指出來，不要照抄。
- 真實資料回歸比較需要使用者提供資料，做不到就在工作單註明「尚未回歸比較」。

## 資料機敏性檢查（每次 commit 前必做）

**這個 repo 是公開的。** 提交前先看清楚要送出去的是什麼，發現疑似機敏或個資
就**停下來問使用者**，不要自己判斷「應該沒關係」。

### 提交前

先列出這次會被提交的新檔案：

```powershell
git add -A -n              # 只列出，不真的加入
git status --short --untracked-files=all
```

逐一對照下列樣態，命中任一項就先問：

| 類別 | 具體例子 |
| --- | --- |
| 真實調查資料 | 軌跡檔（`*_CSV_SU.csv`）、影像、影片、含座標的輸出、車牌、人臉 |
| 客戶或機關文件 | 規格書、契約、標案文件、期中期末報告（`.xlsx`／`.docx`／`.pdf`） |
| 生產環境程式與設定 | 後端服務原始碼、`.env`、連線字串、憑證、金鑰、API token |
| 個資 | 姓名、電話、地址、身分證字號、email、車牌號碼 |
| 內部資訊 | 本機絕對路徑、內部主機名、資料庫名稱、客戶名稱、標案代號 |
| 大型二進位檔 | 超過數 MB 的非程式檔，通常是資料而不是程式 |

問法要具體到選項：**加進 `.gitignore`／改寫成不含實資料的版本／確認可公開**。
不要問「這個可以嗎」，要說明「這是什麼、公開後別人會看到什麼」。

只要是**真實案件的資料**，預設就是不要提交。測試與範例一律用合成的小樣本
（見 `tests/test_motc_su.py` 的 `SAMPLE`），需要真實檔案時由使用者本機提供路徑。

**文件裡也不要寫出真實案件的檔名或路口名稱。** 工作單的「驗證環境與版本」
要記錄用真實檔驗過什麼，但寫法是「本機一份 `*_CSV_SU.csv`，27.8 MB，
四岔路口單一架次」這種不可識別的描述——檔名通常含縣市、路口與架次代號，
等於公開一個調查地點。檔案大小、車輛數、車種分布這些數字可以照實寫。

一併掃一次已追蹤檔案的內容：

```powershell
git ls-files | ForEach-Object { Select-String -Path $_ -Pattern "api[_-]?key|secret|token|password|BEGIN .*PRIVATE KEY|C:\Users" -List }
```

### 如果東西已經被提交了

**`.gitignore` 對已經被追蹤的檔案無效。** 這是最常見的意外：先 commit 了，
之後才把那個路徑加進 `.gitignore`，檔案卻仍然一直被追蹤與推送。每次檢查時
順手比對一次：

```bash
git ls-files | git check-ignore --no-index --stdin
```

**`--no-index` 不能省。** `git check-ignore` 預設會跳過已追蹤的檔案，
沒有這個旗標就永遠查不到東西——而「已追蹤卻已列入 ignore」正是要找的目標。

發現已提交的機敏資料時，**先問使用者要哪一種處理**，不要自己動手：

| 做法 | 效果 | 代價 |
| --- | --- | --- |
| `git rm --cached <檔案>` 後 commit | 停止追蹤，本機檔案保留，**歷史仍留有內容** | 最簡單；適用於「不該再更新，但外洩無實害」 |
| 改寫內容後 commit | 換成不含實資料的版本，**歷史仍留有舊版** | 適用於範例檔想留但不要真資料 |
| `git filter-repo` 重寫歷史後 force push | 從歷史移除 | 會改寫所有 commit SHA，協作者必須重新 clone；GitHub 的 fork 與快取可能仍留有副本 |

三種都要讓使用者知道同一件事：**已經推上公開 repo 的內容必須視為已外洩。**
重寫歷史不等於沒發生過——搜尋引擎、GitHub 的 API 快取、他人的 clone 都可能還在。
如果外洩的是憑證或金鑰，**唯一有效的處理是輪替它**，移除檔案只是清理現場。

## 不要做的事

- 不要為了通過測試而放寬契約；契約要改就先跟使用者確認，並在 catalog 升「契約版」。
- **不要為核心 `traffickit` 新增相依套件**（目前只有 pandas、numpy）；需要時先問。
  視覺化相關的相依（OpenCV、Pillow、tqdm、GUI）一律放 `packages/traffickit-viz`，
  那邊可以有自己的相依，但仍然要先問。
- 不要動 `data/` 裡的舊程式。
- 不要在功能還沒做真實資料回歸比較前，把 catalog 狀態寫成「正式」。
- 不要只改程式不改 docstring——API reference 完全由 docstring 產生，
  改了程式沒改 docstring，網站上就是錯的。
- **不要未經使用者同意就 commit 或 push。** push 到 master 會觸發 Actions
  並更新對外網站，屬於對外動作，每次都要先問。
- **不要把真實案件的資料、客戶文件或生產環境程式加進版控。** 提交前一定要做
  上面那節的機敏性檢查；有疑慮就問，不要自己判斷「應該沒關係」。
- 不要在 `docs/` 之外另開一份交付清單或流程說明；要改流程就改本檔上面那張表。
