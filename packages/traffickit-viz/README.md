# traffickit-viz

TrafficKit 的視覺化與影片輸出層。

> **目前是骨架，還沒有公開函式。** 這一版建立的是套件結構、相依邊界與測試
> 框架，功能會逐項搬進來。想找可以用的東西請看
> [traffickit 本體](../../README.md)。

## 為什麼是獨立的套件

`traffickit` 只依賴 pandas 與 numpy，所以後端服務、CI 與 Jupyter 都裝得動。
視覺化需要 OpenCV（安裝後數百 MB）、影片編解碼，往後還會有 GUI。把這些放進
核心，等於讓每一個只想算轉向流量的人都被迫安裝一整套影像處理相依。

兩個套件放在同一個 repo（monorepo），因為視覺化一定跟著格式層走——格式一改，
這邊就要跟著改。同一個 PR 就能改完兩邊並被同一套 CI 驗證；拆成兩個 repo 的話
每次改格式都要開兩個 PR 並手動對版本。

## 分工

| 放這裡 | 留在 `traffickit` |
| --- | --- |
| 影片解碼與編碼 | 軌跡檔讀取（`traffickit.formats`） |
| bbox 繪製與疊圖 | 交通計算（`speed`、`volume`） |
| 顏色、標籤、箭頭樣式 | 會改變交通結果意義的判定 |
| 比例尺（公尺 → 像素） | 單位契約本身（m/s、秒、公尺） |
| 互動介面與預覽 | — |
| 命令列參數剖析 | — |

判準是「這段邏輯改變的是**畫面**還是**數字**」。改變數字的留在核心，改變畫面
的放這裡。

**相依方向是單向的**：`traffickit_viz` 可以 import `traffickit`，
`traffickit` 永遠不可以 import `traffickit_viz`。核心的
`tests/test_layering.py` 專門守這條線。

## 安裝

兩個套件都還沒上 PyPI，所以**要先裝核心**，pip 才不會為了滿足
`traffickit>=0.1` 跑去 PyPI 找不到而失敗。

開發用（可編輯安裝，改程式不必重裝）：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install -e packages/traffickit-viz
```

從 GitHub 安裝：

```bash
pip install git+https://github.com/YCkao5888/TrafficKit.git
pip install "git+https://github.com/YCkao5888/TrafficKit.git#subdirectory=packages/traffickit-viz"
```

命令列進度條與預覽畫面的加速路徑是選用的，缺了也能跑：

```bash
pip install "traffickit-viz[extras]"
```

> 目前**刻意沒有**在核心提供 `pip install traffickit[viz]` 這個捷徑。
> 那需要在核心的 `optional-dependencies` 寫一筆 `traffickit-viz`，而它還不在
> PyPI 上，寫成 git 直接參照又會讓核心以後上不了 PyPI。等真的要發佈時再補。

## 測試

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s packages/traffickit-viz/tests -v
```

核心的測試不會跑到這裡，這樣沒裝 OpenCV 也能跑核心測試。CI 也是分成兩個 job。

## 預計搬進來的東西

來源是本機的 `data/video_add_veh_bbox.py`（在空拍影片上為指定車輛畫 bbox 並
輸出影片的工具，含 tkinter 介面與命令列）。搬移時的原則：

- 該工具自己的 CSV 讀取器（`load_su_csv`、`load_ssam_csv`）**不搬**，
  改呼叫 `traffickit.formats` 的讀取器。兩份讀取器對同一個檔案的行為並不
  一致，統一之後以核心的嚴格版為準。
- 比例尺預設值（某個架次的 `0.08064`）不進版控。核心不給預設門檻，
  這裡也一樣——填錯比例尺畫出來的框會整體偏移，應該報錯而不是默默套用。
- `_fix_heading_flips`（修正車頭／車尾角點被對調的影格）改變的是**資料的
  意義**不只是畫面，應該進核心的格式層，不是這裡。
