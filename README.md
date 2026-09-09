# TrafficKit

交通分析計算套件。提供可安裝、可呼叫、可驗證的交通計算功能。

網頁後端、Python 桌面程式與批次工具安裝同一份套件，呼叫相同函式。
**套件只負責計算**：資料讀取、單位換算來源、圖表與檔案輸出由呼叫端負責。

- 線上文件：<https://yckao5888.github.io/TrafficKit/latest/>（API reference、功能目錄、工作單）
- 安裝套件名／Python 匯入名：`traffickit`
- 需求：Python ≥ 3.10、pandas 2.2–3.0、numpy ≥ 1.26

## 安裝

開發用（可編輯安裝，改原始碼不必重裝）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

```bash
python -m venv .venv
./.venv/bin/python -m pip install -e .
```

交付用（從 wheel 安裝）：

```powershell
.\.venv\Scripts\python.exe -m pip wheel --no-deps . --wheel-dir dist
.\.venv-check\Scripts\python.exe -m pip install dist/traffickit-0.1.0-py3-none-any.whl
```

## 快速上手

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

轉向流量統計：

```python
from traffickit.volume import DEFAULT_PCU_WEIGHTS, summarise_turn_volume

movements = pd.DataFrame([          # 路口的轉向定義，同時決定哪些轉向合法
    {"entry_gate": "N", "exit_gate": "S", "turn": "straight", "is_allowed": True},
    {"entry_gate": "N", "exit_gate": "E", "turn": "left",     "is_allowed": True},
])
passages = pd.DataFrame([           # 一列一台車
    {"vehicle_id": "V1", "entry_gate": "N", "exit_gate": "S", "vehicle_class": "c"},
    {"vehicle_id": "V2", "entry_gate": "N", "exit_gate": "E", "vehicle_class": "m"},
])

result = summarise_turn_volume(
    passages,
    movements=movements,
    vehicle_groups={"小型車": ["c"], "機車": ["m"]},
    pcu_weights={name: DEFAULT_PCU_WEIGHTS[name] for name in ("小型車", "機車")},
)

result.movements  # 進入 × 駛出 × 轉向 × 分組，合法但 0 台的組合也會保留
result.by_turn    # 進入 × 轉向 × 分組，直接對應報表版面
result.summary    # 總 PCU、未分組車輛數、違規轉向車輛數
```

可執行的完整範例：

```powershell
.\.venv\Scripts\python.exe examples\speed_distribution_demo.py
.\.venv\Scripts\python.exe examples	urn_volume_demo.py
.\.venv\Scripts\python.exe examples\motc_su_turn_volume_demo.py
```

從 MOTC_SU 空拍軌跡檔一路算到轉向流量：

```python
from traffickit.formats import read_motc_su_passages
from traffickit.volume import clockwise_movements, summarise_turn_volume

passages = read_motc_su_passages("...._CSV_SU.csv")   # fps 預設 9.99
complete = passages.query("is_complete")               # 代號 X 是不完整軌跡

movements = clockwise_movements(                       # A/B/C/D 順時針編號
    ["A", "B", "C", "D"],
    disallowed=[(g, g) for g in "ABCD"],               # 合法性要自己填！
)
result = summarise_turn_volume(complete, movements=movements, ...)
```

## 使用前必讀的三個約定

1. **單位一律 m/s、時間一律「相對本資料集共同起點的秒數」。**
   像素／公尺比例尺換算、km/h 顯示是呼叫端的責任。
2. **輸入不乾淨就拋錯，不默默丟資料。** 缺欄位、缺值、負值、重複樣本一律 `ValueError`；
   傳錯型別是 `TypeError`。函式不修改傳入的 DataFrame，也不讀寫檔案。
3. **統計對象是「車」還是「樣本」由各功能明訂。** 分母怎麼算、範圍外的資料算不算，
   都寫在該功能的工作單裡，不要用猜的。
4. **計算功能不碰檔案。** 只有 `traffickit.formats` 會讀檔，而且它只做欄位與
   型別轉換，不做交通判定。

## 功能索引

完整索引與狀態見 [`docs/catalog.md`](docs/catalog.md)。

| 功能 ID | 公開入口 | 用途 | 狀態 |
| --- | --- | --- | --- |
| speed.speed_distribution | `traffickit.speed.summarise_speed_distribution` | 每車代表速度的分布統計與分箱 | 試行 |
| speed.bin_edges | `traffickit.speed.speed_bin_edges` | 產生等寬分箱邊界（多群組共用） | 試行 |
| volume.turn_volume | `traffickit.volume.summarise_turn_volume` | 各進入方向 × 轉向 × 車種分組的車輛數與 PCU | 試行 |
| volume.clockwise_movements | `traffickit.volume.clockwise_movements` | 由順時針路口代號推導轉向對照表 | 試行 |
| formats.motc_su | `traffickit.formats.read_motc_su_passages`、`read_motc_su_tracks` | 讀取 MOTC_SU 空拍影像軌跡 CSV | 試行 |

## 驗證

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 文件

線上版：<https://yckao5888.github.io/TrafficKit/latest/>，
右上角可切換版本。本機建置：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[docs]"
.\.venv\Scripts\python.exe -m sphinx -b html -W --keep-going -d docs\_build\doctrees docs docs\_build\html
start docs\_build\html\index.html
```

API reference 由 docstring 產生。新增或修改功能時要一併更新的項目見
[`docs/release-checklist.md`](docs/release-checklist.md)。

## 專案結構

```
TrafficKit/
├─ README.md                  本檔：套件使用說明
├─ CLAUDE.md                  給 AI 助理的專案慣例與必問事項
├─ pyproject.toml
├─ src/traffickit/            套件原始碼
│   ├─ _validation.py        各功能共用的輸入驗證
│   ├─ formats/              格式轉換層（唯一會讀檔的地方）
│   ├─ speed/                速度相關功能
│   └─ volume/               流量相關功能
├─ examples/                  每個功能一份可執行範例
├─ tests/                     每個功能一份規格測試
├─ .github/workflows/docs.yml  推 master／tag 時建置並部署文件
├─ .claude/skills/            新增功能用的 skill
├─ docs/                      Sphinx 文件原始碼（也是網站內容）
│   ├─ conf.py                Sphinx 設定
│   ├─ index.md               文件首頁
│   ├─ api/                   API reference（autosummary 由 docstring 產生）
│   ├─ switcher.json          版本切換器的來源
│   ├─ release-checklist.md   發行與文件更新檢查表
│   ├─ feature-development-guide.md   開發教學與交付格式（Step 1–8）
│   ├─ feature-request-template.md    擴充功能的需求單模板
│   ├─ catalog.md                     功能索引、狀態定義、與舊程式對照
│   └─ worksheets/                    各功能的工作單與驗證紀錄
└─ data/                      參考用的舊版程式，不參與建置
```

## 要擴充新功能？

1. 複製 [`docs/feature-request-template.md`](docs/feature-request-template.md) 填成需求單。
2. 依 [`docs/feature-development-guide.md`](docs/feature-development-guide.md) 的 Step 1–8 交付。
3. 在 [`docs/catalog.md`](docs/catalog.md) 登記一列，補一份 `docs/worksheets/<功能 ID>.md`，
   並把新函式加進 `docs/api/<子套件>.rst` 的 `autosummary` 清單。
   完整清單見 [`docs/release-checklist.md`](docs/release-checklist.md)。

交給 AI 助理代做時，把需求單（或一份現成程式碼加一句「照這個邏輯做」）給它即可；
[`CLAUDE.md`](CLAUDE.md) 已寫明本專案的慣例、驗證指令，以及資訊不足時它必須回問哪些事。
