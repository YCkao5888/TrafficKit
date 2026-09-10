<h1 align="center">TrafficKit</h1>

<p align="center">
  把交通指標的定義，寫成可安裝、可呼叫、可驗證的 Python 函式。<br>
  <sub>A Python toolkit for reproducible traffic-engineering metrics.</sub>
</p>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![tests](https://github.com/YCkao5888/TrafficKit/actions/workflows/tests.yml/badge.svg)](https://github.com/YCkao5888/TrafficKit/actions/workflows/tests.yml)
[![docs](https://github.com/YCkao5888/TrafficKit/actions/workflows/docs.yml/badge.svg)](https://github.com/YCkao5888/TrafficKit/actions/workflows/docs.yml)
[![status](https://img.shields.io/badge/status-%E8%A9%A6%E8%A1%8C-yellow)](https://yckao5888.github.io/TrafficKit/latest/catalog.html)

</div>

<p align="center">
  <a href="https://yckao5888.github.io/TrafficKit/latest/"><b>線上文件</b></a>
  &nbsp;·&nbsp;
  <a href="https://yckao5888.github.io/TrafficKit/latest/api/index.html"><b>API reference</b></a>
  &nbsp;·&nbsp;
  <a href="https://yckao5888.github.io/TrafficKit/latest/catalog.html"><b>功能目錄</b></a>
  &nbsp;·&nbsp;
  <a href="https://yckao5888.github.io/TrafficKit/latest/worksheets/index.html"><b>工作單</b></a>
</p>

---

同一份交通指標，在網頁後端、桌面程式與批次工具裡常常各寫一次，算出來的數字卻不一樣。
TrafficKit 把「會改變交通結果意義」的邏輯集中成一個套件：**大家安裝同一份、呼叫同一個函式、
得到同一個答案**，而且每個答案都查得到它的定義與驗證紀錄。

```bash
pip install git+https://github.com/YCkao5888/TrafficKit.git
```

```python
from traffickit.formats import read_motc_su_vehicles
from traffickit.volume import clockwise_movements, summarise_turn_volume

vehicles = read_motc_su_vehicles("....CSV_SU.csv")          # 讀空拍軌跡檔
movements = clockwise_movements(["A", "B", "C", "D"])       # 順時針編號推轉向
result = summarise_turn_volume(vehicles.query("is_complete"), movements=movements, ...)

result.by_turn    # 進入方向 × 轉向 × 車種分組的車輛數與 PCU
result.summary    # 總 PCU、未分組車輛數、違規轉向車輛數
```

## 這個套件跟自己寫一份的差別

- **每個數字都說得出分母。** 統計對象是「車」還是「樣本」、範圍外的資料算不算、
  不符合條件的對象留不留在分母，全部明文寫在契約裡，不靠讀原始碼推測。
- **資料不乾淨就拋錯，不默默丟掉。** 缺欄位、負值、重複樣本一律 `ValueError`。
  少算了幾台車一定看得見，不會安靜地變成一份看起來正常的報表。
- **未定義的統計量回 `None`，不填 0。** 單一車輛的標準差就是未定義；
  填 0 會被讀成「速度很一致」。
- **計算與讀檔分層。** 計算功能零 I/O，可以直接接後端、資料庫或測試資料；
  只有 `traffickit.formats` 會碰檔案，而且它不做任何交通判定。
- **每個功能都有工作單。** 完整契約、手算範例、實跑的效能數字、
  以及「還有什麼沒驗證」，全部寫在文件裡。

## 目錄

- [安裝](#安裝)
- [快速上手](#快速上手)
- [功能索引](#功能索引)
- [設計約定](#設計約定)
- [文件](#文件)
- [開發](#開發)
- [授權](#授權)

## 安裝

需求：Python ≥ 3.10、pandas 2.2–3.0、numpy ≥ 1.26。

```bash
pip install git+https://github.com/YCkao5888/TrafficKit.git
```

從原始碼開發（可編輯安裝，改程式不必重裝）：

```powershell
git clone https://github.com/YCkao5888/TrafficKit.git
cd TrafficKit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

```bash
git clone https://github.com/YCkao5888/TrafficKit.git
cd TrafficKit
python -m venv .venv
./.venv/bin/python -m pip install -e .
```

## 快速上手

### 車速分布統計

```python
import pandas as pd
from traffickit.speed import speed_bin_edges, summarise_speed_distribution

tracks = pd.DataFrame({
    "vehicle_id": ["A", "A", "B", "B"],
    "time_s": [0.0, 1.0, 0.0, 1.0],
    "speed_smooth_mps": [8.0, 10.0, 11.0, 12.0],
})

edges = speed_bin_edges(width_mps=5.0, upper_mps=15.0)
result = summarise_speed_distribution(
    tracks, bin_edges_mps=edges, statistic="mean", moving_threshold_mps=2.0
)

result.bins            # 一列一箱：bin_index / lower_mps / upper_mps / vehicle_count / proportion
result.vehicle_speeds  # 一列一車：可用來畫箱形圖或自行分車種彙整
result.summary         # mean / std / min / median / p85 / max
```

分箱與統計的對象都是**車**，不是樣本——停留較久的車不會被重複計數。

<details>
<summary><b>轉向流量統計（含 PCU）</b></summary>

<br>

`movements` 同時決定三件事：轉向類別怎麼查、報表要列出哪些格子、哪些轉向合法。
因此輸出能區分「合法但 0 台」與「這個方向不允許轉」。

```python
import pandas as pd
from traffickit.volume import DEFAULT_PCU_WEIGHTS, summarise_turn_volume

movements = pd.DataFrame([
    {"entry_gate": "N", "exit_gate": "S", "turn": "straight", "is_allowed": True},
    {"entry_gate": "N", "exit_gate": "E", "turn": "left",     "is_allowed": True},
])
vehicles = pd.DataFrame([           # 一列一台車
    {"vehicle_id": "V1", "entry_gate": "N", "exit_gate": "S", "vehicle_class": "c"},
    {"vehicle_id": "V2", "entry_gate": "N", "exit_gate": "E", "vehicle_class": "m"},
])

result = summarise_turn_volume(
    vehicles,
    movements=movements,
    vehicle_groups={"小型車": ["c"], "機車": ["m"]},
    pcu_weights={name: DEFAULT_PCU_WEIGHTS[name] for name in ("小型車", "機車")},
)

result.movements  # 進入 × 駛出 × 轉向 × 分組，合法但 0 台的組合也會保留
result.by_turn    # 進入 × 轉向 × 分組，直接對應報表版面
result.summary    # 總 PCU、未分組車輛數、違規轉向車輛數
```

`DEFAULT_PCU_WEIGHTS` 取自既有調查工具的設定值，**必須明確傳入**；
本套件不認定它等同任何法規或手冊的規定值。

</details>

<details>
<summary><b>從 MOTC_SU 空拍軌跡檔一路算到轉向流量</b></summary>

<br>

```python
from traffickit.formats import read_motc_su_vehicles
from traffickit.volume import clockwise_movements, summarise_turn_volume

vehicles = read_motc_su_vehicles("....CSV_SU.csv")     # fps 預設 9.99
complete = vehicles.query("is_complete")                # 代號 X 是不完整軌跡

movements = clockwise_movements(                        # A/B/C/D 順時針編號
    ["A", "B", "C", "D"],
    disallowed=[(g, g) for g in "ABCD"],                # 合法性要依現場填！
)
result = summarise_turn_volume(
    complete,
    movements=movements,
    vehicle_groups={"大型車": ["b", "t", "h"], "小型車": ["c"], "機車": ["m"]},
    pcu_weights=DEFAULT_PCU_WEIGHTS,
)
```

不完整軌跡（代號 `X`）會照樣讀入並標記 `is_complete=False`，不會默默消失——
過濾掉幾台是呼叫端的決定，而且看得見。

`clockwise_movements` 只推導轉向的**幾何類別**，不知道現場的管制規定；
產生的表格預設全部允許，迴轉等限制必須自己填進 `disallowed`。

</details>

可執行的完整範例：

```powershell
.\.venv\Scripts\python.exe examples\speed_distribution_demo.py
.\.venv\Scripts\python.exe examples\turn_volume_demo.py
.\.venv\Scripts\python.exe examples\motc_su_turn_volume_demo.py
```

## 功能索引

完整索引、狀態定義與契約版規則見[功能目錄](https://yckao5888.github.io/TrafficKit/latest/catalog.html)。

| 功能 ID | 公開入口 | 用途 | 狀態 |
| --- | --- | --- | --- |
| speed.speed_distribution | `traffickit.speed.summarise_speed_distribution` | 每車代表速度的分布統計與分箱 | 試行 |
| speed.bin_edges | `traffickit.speed.speed_bin_edges` | 產生等寬分箱邊界（多群組共用） | 試行 |
| volume.turn_volume | `traffickit.volume.summarise_turn_volume` | 各進入方向 × 轉向 × 車種分組的車輛數與 PCU | 試行 |
| volume.clockwise_movements | `traffickit.volume.clockwise_movements` | 由順時針路口代號推導轉向對照表 | 試行 |
| formats.motc_su | `traffickit.formats.read_motc_su_vehicles`、`read_motc_su_tracks` | 讀取 MOTC_SU 空拍影像軌跡 CSV | 試行 |

**「試行」代表契約已定稿、測試與範例都通過，但尚未與既有系統做真實資料回歸比較。**
介面仍可能調整，變更會列在功能目錄的契約變更紀錄裡。

## 設計約定

呼叫任何功能前先知道這四件事：

1. **單位一律 m/s，時間一律「相對本資料集共同起點的秒數」。**
   像素／公尺比例尺換算、km/h 顯示是呼叫端的責任。
2. **輸入不乾淨就拋錯，不默默丟資料。** 缺欄位、缺值、負值、重複樣本一律 `ValueError`；
   型別錯是 `TypeError`。函式不修改傳入的 DataFrame。
3. **統計對象是「車」還是「樣本」由各功能明訂。** 分母怎麼算、範圍外的資料算不算，
   都寫在該功能的工作單裡，不要用猜的。
4. **計算功能不碰檔案。** 只有 `traffickit.formats` 會讀檔，而且它只做欄位與型別轉換，
   不做交通判定。

## 文件

<https://yckao5888.github.io/TrafficKit/latest/>，右上角可切換版本。
每個發行版的文件在發佈後就不再變動，客戶裝哪一版就查哪一版。

| 內容 | 用途 |
| --- | --- |
| [API reference](https://yckao5888.github.io/TrafficKit/latest/api/index.html) | 每個公開函式的參數、回傳、例外與注意事項，由 docstring 產生 |
| [功能目錄](https://yckao5888.github.io/TrafficKit/latest/catalog.html) | 功能索引、狀態定義、契約版規則、與舊程式的差異對照 |
| [工作單](https://yckao5888.github.io/TrafficKit/latest/worksheets/index.html) | 完整契約、手算範例、實跑的驗證紀錄與已知限制 |
| [開發指南](https://yckao5888.github.io/TrafficKit/latest/feature-development-guide.html) | 新增一個交通功能的八個步驟與交付格式 |

本機建置：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[docs]"
.\.venv\Scripts\python.exe -m sphinx -b html -W --keep-going -d docs\_build\doctrees docs docs\_build\html
start docs\_build\html\index.html
```

## 開發

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

要新增或修改功能，先讀[開發指南](https://yckao5888.github.io/TrafficKit/latest/feature-development-guide.html)，
並複製 [`docs/feature-request-template.md`](docs/feature-request-template.md) 填成需求單，
把交通定義（統計對象、分母、邊界比較、同值取捨）講清楚再動手寫程式。
交付清單與各項慣例在 [`CLAUDE.md`](CLAUDE.md)。

<details>
<summary><b>專案結構</b></summary>

<br>

```
TrafficKit/
├─ src/traffickit/            套件原始碼
│   ├─ _validation.py         各功能共用的輸入驗證
│   ├─ formats/               格式轉換層（唯一會讀檔的地方）
│   ├─ speed/                 速度相關功能
│   └─ volume/                流量相關功能
├─ examples/                  每個功能一份可執行範例
├─ tests/                     每個功能一份規格測試
├─ docs/                      Sphinx 文件原始碼，也就是網站內容
│   ├─ api/                   API reference（autosummary 由 docstring 產生）
│   ├─ catalog.md             功能索引、狀態定義、與舊程式對照
│   ├─ worksheets/            各功能的工作單與驗證紀錄
│   ├─ feature-development-guide.md   開發教學與交付格式
│   ├─ feature-request-template.md    擴充功能的需求單模板
│   └─ release-checklist.md   發行與文件更新檢查表
├─ CLAUDE.md                  專案慣例、交付清單、機敏性檢查
└─ .github/workflows/         測試 CI 與文件建置部署
```

`data/` 放舊版參考程式與真實調查資料，**已列入 `.gitignore`，只存在於開發者本機**。
真實案件的資料不進版控；測試與範例一律使用合成的小樣本。

</details>

## 授權

[MIT](LICENSE)
