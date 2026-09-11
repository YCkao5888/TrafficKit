# traffickit-viz

TrafficKit 的視覺化與影片輸出層。

> 交通計算請看 [traffickit 本體](../../README.md)。

## 圖形介面

```powershell
traffickit-viz
# 或
.\.venv\Scripts\python.exe -m traffickit_viz.gui
```

版面的原則是**預覽最大、設定最小**：中央永遠是你要確認的那張圖，左邊選車，
下面一條是設定。常用的四個外觀選項（標籤、車頭標示、框線粗細、車頭顏色）
留在外面，其餘收在「進階」裡。

跟舊的 tkinter 介面比，改掉的是這幾件事：

| 舊工具 | 現在 |
| --- | --- |
| 改了設定要按「套用目前設定」預覽才更新 | **設定一動就重畫**——單格成本很低，做得到 |
| 車輛是一個純清單框，上千台時找不到車 | 可搜尋、可依車種篩選、可只看完整軌跡 |
| 顏色設定超過 40 台就不再個別顯示 | 色塊直接畫在清單上，沒有數量上限 |
| 訊息只能印在文字區 | 狀態列直接寫「幾台車、不完整幾台、行穿線幾台」 |
| 十幾個外觀欄位平鋪在主畫面 | 常用的在外，其餘收進「進階」 |

介面背後的狀態與計算集中在 `traffickit_viz.gui._session`，**完全不依賴 Qt**，
所以那一層可以直接寫測試；視窗只負責把動作轉成呼叫、把結果畫出來。

**目前只讀 MOTC_SU（Pixel Frame）格式。** SSAM 版的座標是公尺，要疊到影片上
需要比例尺換算，那一層還沒做——與其給一個會讓框整體偏移的預設比例尺，
不如先不提供。

預覽是**可拖曳的靜態畫面**（拖到哪一格就畫哪一格），還沒有播放功能。

## 為什麼是獨立的套件

`traffickit` 只依賴 pandas 與 numpy，所以後端服務、CI 與 Jupyter 都裝得動。
這邊需要 OpenCV 與 Qt，兩者加起來幾百 MB。把它們放進核心，等於讓每一個只想
算轉向流量的人都被迫安裝一整套影像處理與視窗系統。

**Qt（PySide6）是本套件的必要相依**，不是選用的：使用者不必記 extras 就有
介面。代價是後端與批次也會裝到 Qt。不過 `import traffickit_viz` **不會載入
Qt**——只有真的開介面時才會，所以只付體積、不付載入時間，
`tests/test_package.py` 有一支測試在守這件事。

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
| 互動介面與預覽（Qt） | — |
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

裝完之後 `traffickit-viz` 這個指令就可以開介面。

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
| **軌跡準備** | |
| `resample_tracks(tracks, frames, *, interpolate, max_gap)` | 把軌跡補到影片的每一格；間隔過大的區段不補 |
| `add_headings(tracks, *, window, order_by)` | 由四角點推出車頭方向並沿時間平滑 |
| `frame_span(tracks, *, vehicle_ids, pad)` | 這些車出現的影格範圍 |
| **外觀** | |
| `assign_colors(vehicle_ids, *, palette, overrides)` | 配色，**整段影片一次算好** |
| `BoxStyle(colors, ...)` / `default_style(vehicle_ids, **options)` | 框線、標籤、填色、車頭標示 |
| `parse_color` / `color_to_hex` | 顏色寫法與 BGR 的互轉 |
| **輸出** | |
| `probe_video(path)` | 讀幀率、影格數、尺寸，不解碼畫面 |
| `draw_boxes(image, boxes, *, style)` | 把一個影格的框畫到影像上 |
| `render_video(video, tracks, *, style, ...)` | 整段疊框輸出成新影片，回傳 `RenderResult` |
| `resolve_output_path(...)` | 依 codec 決定副檔名、自動命名 |
| `parse_time_spec(spec, fps)` / `resolve_center_range(...)` | `"01:30"`、`"12.5s"` → 影格；事件前後取一段 |

```python
from traffickit.formats import read_motc_su_tracks
from traffickit_viz import (
    BoxStyle, add_headings, assign_colors, frame_span,
    render_video, resample_tracks,
)

tracks = read_motc_su_tracks("your_file_CSV_SU.csv")
start, end = frame_span(tracks)

# 順序很重要：先補格，再算方向。
dense = resample_tracks(tracks, range(start, end + 1), max_gap=30)
dense = add_headings(dense, window=5)

style = BoxStyle(assign_colors(sorted(dense["vehicle_id"].unique())), front="arrow")
result = render_video("aerial.mp4", dense, style=style, show_frame_number=True)
print(result.output_path, result.frames_written, result.missing_vehicle_ids)
```

可執行範例：

```powershell
# 畫一個影格存成 PNG
.\.venv\Scripts\python.exe packages/traffickit-viz/examples/draw_frame_demo.py
# 合成一小段影片並疊框輸出（不給參數時自己造素材）
.\.venv\Scripts\python.exe packages/traffickit-viz/examples/render_video_demo.py
```

可用的 codec：`MJPG`（.avi，最快、預設）、`XVID`（.avi，壓縮率好）、
`mp4v`（.mp4，相容性佳）。副檔名依 codec 自動修正。

### 四個要知道的約定

1. **`draw_boxes` 就地修改影像。** 這是整個套件唯一會修改輸入的地方——
   影片一秒數十張 4K 影像，每張都複製一份會慢到不能用。需要保留原圖請自己
   傳 `image.copy()`。表格類的函式（`add_headings`）仍然不修改輸入。
2. **配色要一次算好整段影片。** 若在繪製時才依當下影格出現的車輛順序配色，
   同一台車的顏色會隨別的車進出畫面而改變，畫面會閃爍且不會有錯誤訊息。
   `draw_boxes` 因此要求顏色表涵蓋所有要畫的車，缺了就拋錯。
3. **樣式參數有預設值**，與核心「不給預設門檻」的規則不同。差別在猜錯的
   後果：核心的門檻猜錯會算出看起來正常的錯數字；這裡猜錯只是線粗一點，
   看一眼就知道。
4. **本套件不 print、不寫 log。** 進度用 `progress` 回呼，結果讀
   `RenderResult`。要顯示成什麼樣子是呼叫端的事。

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
車頭方向平滑（`_smoothed_heading` → `add_headings`）、顏色剖析與配色、
軌跡內插（`VehicleTrack.resample` → `resample_tracks`）、
影片輸出（`render_video`）、時間寫法剖析、輸出檔命名。

介面用 PySide6（Qt 6）重寫，不是移植 tkinter 版。

還沒搬：預覽播放（目前是可拖曳的靜態畫面）、命令列、軌跡尾巴（`--trail`）、
其他車輛淡色顯示（`--show-others`）、CSV_SSAM 的比例尺換算。

移植時修掉的兩個舊行為：

- 舊工具把標籤位置無條件夾進畫面內，結果**完全在畫面外的車也會在邊緣留下
  一個沒有框的標籤**。現在整台跳過；部分露出的車照畫。
- 舊工具的 `max_gap` 會連**實際有取樣到**的影格一起丟掉（落在寬間隔兩端的
  那兩格）。那是真的偵測結果，不是補出來的框。現在只丟補出來的。

還沒搬的一項效能處理：舊工具用一條讀取執行緒加佇列，讓解碼與編碼重疊。
目前是循序處理，正確但較慢，等真的卡到再補。
