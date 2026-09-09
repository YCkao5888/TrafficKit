# TrafficKit

交通分析計算套件。提供可安裝、可呼叫、可驗證的交通計算功能。

網頁後端、Python 桌面程式與批次工具安裝同一份套件，呼叫相同函式。
**套件只負責計算**：資料讀取、單位換算來源、圖表與檔案輸出由呼叫端負責。

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

可執行的完整範例：

```powershell
.\.venv\Scripts\python.exe examples\speed_distribution_demo.py
```

## 使用前必讀的三個約定

1. **單位一律 m/s、時間一律「相對本資料集共同起點的秒數」。**
   像素／公尺比例尺換算、km/h 顯示是呼叫端的責任。
2. **輸入不乾淨就拋錯，不默默丟資料。** 缺欄位、缺值、負值、重複樣本一律 `ValueError`；
   傳錯型別是 `TypeError`。函式不修改傳入的 DataFrame，也不讀寫檔案。
3. **統計對象是「車」還是「樣本」由各功能明訂。** 分母怎麼算、範圍外的資料算不算，
   都寫在該功能的工作單裡，不要用猜的。

## 功能索引

完整索引與狀態見 [`docs/catalog.md`](docs/catalog.md)。

| 功能 ID | 公開入口 | 用途 | 狀態 |
| --- | --- | --- | --- |
| speed.speed_distribution | `traffickit.speed.summarise_speed_distribution` | 每車代表速度的分布統計與分箱 | 試行 |
| speed.bin_edges | `traffickit.speed.speed_bin_edges` | 產生等寬分箱邊界（多群組共用） | 試行 |

## 驗證

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 專案結構

```
TrafficKit/
├─ README.md                  本檔：套件使用說明
├─ CLAUDE.md                  給 AI 助理的專案慣例與必問事項
├─ pyproject.toml
├─ src/traffickit/            套件原始碼（<領域>/_<功能>.py）
├─ examples/                  每個功能一份可執行範例
├─ tests/                     每個功能一份規格測試
├─ docs/
│   ├─ feature-development-guide.md   開發教學與交付格式（Step 1–8）
│   ├─ feature-request-template.md    擴充功能的需求單模板
│   ├─ catalog.md                     功能索引、狀態定義、與舊程式對照
│   └─ worksheets/                    各功能的工作單與驗證紀錄
└─ data/                      參考用的舊版程式，不參與建置
```

## 要擴充新功能？

1. 複製 [`docs/feature-request-template.md`](docs/feature-request-template.md) 填成需求單。
2. 依 [`docs/feature-development-guide.md`](docs/feature-development-guide.md) 的 Step 1–8 交付。
3. 在 [`docs/catalog.md`](docs/catalog.md) 登記一列，並補一份 `docs/worksheets/<功能 ID>.md`。

交給 AI 助理代做時，把需求單（或一份現成程式碼加一句「照這個邏輯做」）給它即可；
[`CLAUDE.md`](CLAUDE.md) 已寫明本專案的慣例、驗證指令，以及資訊不足時它必須回問哪些事。
