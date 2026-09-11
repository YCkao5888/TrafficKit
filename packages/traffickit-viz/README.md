# traffickit-viz

TrafficKit 的視覺化與影片輸出層。

> **目前只有繪製層。** 讀寫影片檔與互動介面還沒搬進來，功能逐項移植中。
> 交通計算請看 [traffickit 本體](../../README.md)。

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

## 公開函式

| 名稱 | 用途 |
| --- | --- |
| `add_headings(tracks, *, window, order_by)` | 由四角點推出車頭方向並沿時間平滑，多出 `heading_x`／`heading_y` 兩欄 |
| `assign_colors(vehicle_ids, *, palette, overrides)` | 替一批車輛配色，**整段影片一次算好** |
| `BoxStyle(colors, ...)` | 框線粗細、標籤、填色、車頭標示等外觀設定 |
| `default_style(vehicle_ids, **options)` | 用預設配色建樣式的起手式 |
| `draw_boxes(image, boxes, *, style)` | 把一個影格的車輛框畫到影像上 |
| `parse_color` / `color_to_hex` | 顏色寫法與 BGR 的互轉 |

```python
from traffickit.formats import read_motc_su_tracks
from traffickit_viz import BoxStyle, add_headings, assign_colors, draw_boxes

tracks = add_headings(read_motc_su_tracks("your_file_CSV_SU.csv"))
style = BoxStyle(assign_colors(sorted(tracks["vehicle_id"].unique())), front="arrow")

draw_boxes(image, tracks.query("frame == 100"), style=style)   # image 就地被改
```

可執行範例（會輸出一張 PNG）：

```powershell
.\.venv\Scripts\python.exe packages/traffickit-viz/examples/draw_frame_demo.py
```

### 三個要知道的約定

1. **`draw_boxes` 就地修改影像。** 這是整個套件唯一會修改輸入的地方——
   影片一秒數十張 4K 影像，每張都複製一份會慢到不能用。需要保留原圖請自己
   傳 `image.copy()`。表格類的函式（`add_headings`）仍然不修改輸入。
2. **配色要一次算好整段影片。** 若在繪製時才依當下影格出現的車輛順序配色，
   同一台車的顏色會隨別的車進出畫面而改變，畫面會閃爍且不會有錯誤訊息。
   `draw_boxes` 因此要求顏色表涵蓋所有要畫的車，缺了就拋錯。
3. **樣式參數有預設值**，與核心「不給預設門檻」的規則不同。差別在猜錯的
   後果：核心的門檻猜錯會算出看起來正常的錯數字；這裡猜錯只是線粗一點，
   看一眼就知道。

## 測試

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s packages/traffickit-viz/tests -v
```

核心的測試不會跑到這裡，這樣沒裝 OpenCV 也能跑核心測試。CI 也是分成兩個 job。

繪製的測試驗的是**看得出差別的性質**：該被塗到的像素有沒有變、不該被碰的
有沒有保持原樣、缺資料時會不會拋錯。車頭方向的期望值則全部手算。

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

已搬進來的：`RenderOptions` → `BoxStyle`、bbox 與標籤繪製、車頭標示、
車頭方向平滑（`_smoothed_heading` → `add_headings`）、顏色剖析與配色。

移植時修掉的一個舊行為：舊工具把標籤位置無條件夾進畫面內，結果**完全在
畫面外的車也會在邊緣留下一個沒有框的標籤**。現在整台跳過；部分露出的車
照畫。
