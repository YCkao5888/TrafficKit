---
name: new-traffic-feature
description: 在 TrafficKit 新增一個交通計算功能、修改既有功能的契約，或新增一種輸入格式時使用。走完契約確認、實作、範例、測試、功能目錄、工作單、API reference 與驗收的八項交付清單。使用者說「新增功能」「模組化這支程式」「照這個邏輯做一個函式」「改某個功能的算法」時適用。
---

# 新增／修改 TrafficKit 交通功能

專案的程式碼慣例、錯誤政策與分層規則在根目錄的 `CLAUDE.md`，**動手前先讀**。
本 skill 負責流程與交付完整性。

## 第一步：先確認契約，不要先寫程式

1. 讀 `docs/catalog.md`，確認要做的事與既有功能是否重疊，
   能不能只加一個可選參數解決。
2. 讀最接近的既有功能當範本（`speed.speed_distribution` 最完整）。
3. 把 I/O 契約與**三個手算案例**（成立／不成立／邊界）寫出來，先給使用者確認。
4. 下列事項**不可自行假設**，一次問完（不要來回擠牙膏）：

   - 統計對象與分母：每車一筆、每樣本一筆，還是每事件一筆？不符合條件的要不要留在分母？
   - 邊界比較：`>` 還是 `>=`？區間左閉右開還是兩端都含？
   - 同值時取誰：最早時間、最大值，還是全部回傳？
   - 時間範圍：先切時段再計算，還是先計算再篩選？兩者答案不同。
   - 前置條件：輸入是否已平滑／已換算單位／已切 ROI？誰負責？
   - 無效資料：缺值、負值、離群值要拋錯還是排除？排除的話怎麼回報數量與原因？
   - 路口幾何與管制（若與轉向有關）：分支是否順時針編號、哪些轉向合法。
   - **負責人**：這個功能在 `docs/catalog.md` 的「負責人」欄填誰。**每次都問，不要沿用上一次的答案。**

   問題要具體到「兩個選項各會得到什麼答案」。

## 第二步：八項交付，缺一不可

| # | 產出 | 位置 |
| --- | --- | --- |
| 1 | 實作 | `src/traffickit/<領域>/_<功能>.py` |
| 2 | 公開匯出 | `src/traffickit/<領域>/__init__.py` 的 `__all__` |
| 3 | 可執行範例 | `examples/<功能>_demo.py` |
| 4 | 規格測試 | `tests/test_<功能>.py` |
| 5 | 功能目錄 | `docs/catalog.md` 新增或修改一列＋說明段落 |
| 6 | 工作單 | `docs/worksheets/<功能 ID>.md`，並加進 `docs/worksheets/index.md` 的 toctree |
| 7 | **API reference** | `docs/api/<子套件>.rst` 的 `autosummary` 加上名稱 |
| 8 | 驗證紀錄 | 工作單的「驗證環境與版本」表，填**實際跑出來**的數字 |

第 7 項容易漏。**API reference 的內容完全由 docstring 產生**，
所以「寫好 docstring」與「把名稱加進 autosummary 清單」是兩件事，都要做：

- 函式或 dataclass 加在對應子套件頁面的 `autosummary` 區塊。
- 模組層級常數用 `.. autodata::`。
- 新的子套件要建一頁 `docs/api/<名稱>.rst`，並加進 `docs/api/index.rst` 的 toctree
  與分層表格。
- docstring 用 NumPy 格式、繁體中文，必含 Parameters／Returns／Raises／Notes；
  Notes 要寫明「這個功能不做什麼」。

### 繁體中文 docstring 的 RST 陷阱

行內標記的結束符後面**不能直接接中文字或全形開括號**，否則 Sphinx 會報
「Inline literal / strong start-string without end-string」：

```
壞：**嚴格大於**門檻的樣本
壞：``None``（樣本標準差未定義）
好：**比較是嚴格大於，等於門檻不算**。
好：``None``：樣本標準差未定義。
```

結束符後面接 `。`、`，`、`：`、半形空白都可以。

## 第三步：驗收

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[docs]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe examples\<功能>_demo.py
.\.venv\Scripts\python.exe -m sphinx -b html -W --keep-going docs docs\_build\html
```

文件建置用 `-W`，警告即失敗。四項都綠燈才算完成。

交付一個版本時另外走 `docs/release-checklist.md`（改版號、更新
`docs/switcher.json`、打 tag）。

## 契約版與狀態

- 改了輸入欄位、輸出欄位、判定規則或統計口徑 → **契約版 +1**，
  並在 `docs/catalog.md` 的「契約變更紀錄」列出差異與對呼叫端的影響。
- 新增可選參數且預設行為完全不變 → 契約版不動。
- 狀態四階段：草擬／試行／正式／淘汰。**沒做真實資料回歸比較就不可以寫「正式」。**
  新功能交付完成通常落在「試行」。

## 從舊程式移植時

- 逐項列出新舊差異，寫進 `docs/catalog.md` 的對照表，並請使用者確認每一項是預期的。
- 舊程式的 UI 預設值、客戶路徑、比例尺讀取、欄位名稱差異，都留在應用端。
- **「與舊版輸出相同」不等於交通定義正確。** 舊版的可疑行為要指出來，不要照抄
  （既有例子：把未定義的統計量填 0、把範圍外的資料從分母中消掉）。
- 拿不到真實資料回歸比較時，在工作單明確寫「尚未回歸比較」，不要假裝驗過。

## 不要做的事

- 不要為了讓測試通過而放寬契約；契約要改先問使用者，並升契約版。
- 不要新增執行期相依套件（目前只有 pandas、numpy）；需要時先問。
- 不要把讀檔塞進計算功能——新的輸入格式一律放 `traffickit.formats`。
- 不要動 `data/` 裡的舊版參考程式。
