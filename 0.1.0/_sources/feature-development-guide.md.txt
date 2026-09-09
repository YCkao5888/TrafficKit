# 交通分析功能模組開發教學

> 對象：負責 Python 交通算法與分析功能的工程師。  
> 用途：本文件是 TrafficKit 的**開發約定與交付格式**，每新增一個交通功能都沿用 Step 1–8。  
> 套件的使用說明在專案根目錄的 [`README.md`](https://github.com/YCkao5888/TrafficKit#readme)；功能索引在 [`catalog.md`](catalog.md)。

**閱讀前先知道四件事：**

1. 本文中的 `detect_overspeed`（超速判定）是**教學範例，尚未實作**。它示範交付格式，不是可呼叫的功能。
2. 實際交付的第一個功能是 `speed.speed_distribution`（車速分布統計）。想看真實範本，請直接對照
   [`docs/worksheets/speed.speed_distribution.md`](worksheets/speed.speed_distribution.md)
   與 `src/traffickit/speed/_distribution.py`。
3. 已交付的第二個功能是 `volume.turn_volume`（轉向流量統計），
   工作單見 [`docs/worksheets/volume.turn_volume.md`](worksheets/volume.turn_volume.md)。
4. **Step 3（建立套件骨架）只在從零開始時需要，本專案已完成。** 擴充既有功能請跳過 Step 3，
   並改看下一節「要新增一個功能時，實際流程是什麼」。

## 要新增一個功能時，實際流程是什麼

骨架已存在，每次只新增一項能力，重複 Step 1、2、4、5、6、7、8。

| 順序 | 做什麼 | 產出 |
| --- | --- | --- |
| 1 | 填一份需求單，把交通定義講清楚 | [`docs/feature-request-template.md`](feature-request-template.md) 的副本 |
| 2 | 確認 I/O 契約與手算答案（Step 1–2） | 需求單上的欄位表、判定規則、三個手算案例 |
| 3 | 實作（Step 4） | `src/traffickit/<領域>/_<功能>.py` + 在 `__init__.py` 匯出 |
| 4 | 範例（Step 5） | `examples/<功能>_demo.py` |
| 5 | 測試（Step 6） | `tests/test_<功能>.py`，把手算答案變成測試 |
| 6 | 登記（Step 7） | `docs/catalog.md` 新增一列 + `docs/worksheets/<功能 ID>.md` 工作單 |
| 7 | 驗收（Step 8） | wheel 建置、乾淨環境安裝、範例與測試重跑、填驗證紀錄 |

**要請 AI 助理代做時**，把需求單（或一份現成程式碼＋一句「照這個邏輯做」）交出去即可；
專案慣例、驗證指令與必問事項寫在根目錄的 [`CLAUDE.md`](https://github.com/YCkao5888/TrafficKit/blob/master/CLAUDE.md)，助理會依此執行並在資訊不足時回問。

---

# 教學正文：以 detect_overspeed 為例

以下是完整的八步交付格式。範例功能為超速判定，**尚未實作**；重點在格式，不在這個算法。

完成本教學後，其他工程師應能這樣使用你的功能：

```python
from traffickit.speed import detect_overspeed

events = detect_overspeed(tracks, threshold_mps=50 / 3.6)
```

你交付的是 Python 套件中的交通計算能力。網頁後端、Python 桌面程式及批次工具都可以安裝同一份套件，呼叫相同函式。

本文件以先前提供的非號誌路口程式為概念起點，但下列程式是獨立教學範例，並非四個既有情境程式的完整重構。輸入欄位、錯誤處理、同速時的選取規則是本範例明訂的契約；移植舊程式時應先核對差異。

## 開始前：你負責什麼？

交通功能工程師要交付四項東西：**功能規格、計算程式、呼叫範例、驗證資料與測試**。交付完成的判準是：其他工程師只看文件與範例，就能呼叫並理解結果。

| 工作 | 主要負責者 | 具體例子 |
| --- | --- | --- |
| 交通定義與計算方法 | 交通功能工程師 | 平滑速度如何取得、超速使用 `>` 或 `>=`、每車或每事件計數 |
| 輸入與輸出規格、品質要求 | 交通功能工程師 | 欄位型別、m/s、時間基準、缺值處理、錯誤訊息 |
| 計算函式與正確性驗證 | 交通功能工程師 | 超速判定、PET、統計分母、已知答案的小樣本 |
| 客戶格式轉換與資料存取 | 後端／整合工程師，依交通規格實作 | 讀取 CSV、欄位對照、單位轉換、資料庫查詢 |
| 操作介面與圖表呈現 | 前端／桌面工程師 | 篩選控制、事件表、地圖、圖表樣式 |
| 執行、API、檔案輸出與部署 | 後端／整合工程師 | 任務排程、JSON、CSV 下載、安裝套件、執行監控 |

實際寫程式的人可以兼任。判斷程式應放在哪裡時，看它的責任：**會改變交通結果意義的邏輯，放在交通功能；管理操作、傳輸或儲存的邏輯，放在應用端。**

第一版使用普通 Python 函式即可。套件的領域分類、公開介面與內部實作區分，參考 [SciPy 的 API 設計](https://docs.scipy.org/doc/scipy/reference/index.html)。我們借用這種組織方式，並不需要依賴 SciPy 才能建立自己的套件。

## Step 1：先圈定一件能驗證的交通工作

**本步產出：一句目的、一份納入範圍、一份排除範圍。**

第一個功能定義為：

> 給定同一份資料集內、已完成速度平滑的軌跡資料與速度門檻，找出最高平滑速度超過門檻的車輛，每車回傳一筆代表資料。

| 本功能負責 | 呼叫端或其他功能負責 |
| --- | --- |
| 檢查必要欄位與無效資料 | 讀取 CSV、metadata 或資料庫 |
| 找出每台車最高平滑速度 | 速度平滑與其參數設定 |
| 依門檻判定並回傳資料表 | 選取哪個路口、方向或分析時段 |
| 固定同速選取及輸出排序 | 儲存 CSV、產生 API 回應、畫圖 |

本例直接分析傳入資料的全部時間範圍，不推定這些資料已經位於路口內，也不自行裁切 ROI。呼叫端必須知道自己傳入的分析範圍。

**最小功能的判準：可以獨立說明輸入、輸出與判定規則，並用小樣本驗證。** 一個功能可以包含數個內部函式；一個指標代碼也不一定要對應一份獨立算法。

完成條件：你能回答「給什麼資料、算什麼、回傳什麼」，且答案中不需要提到網頁、資料庫或輸出資料夾。

## Step 2：先定義 I/O 與預期答案

**本步產出：功能契約。第一版就使用以下規格。**

### 輸入資料

使用 `pandas.DataFrame`。一列是一台車在一個時間點的資料。

| 欄位 | 型別 | 單位／基準 | 規則 |
| --- | --- | --- | --- |
| `vehicle_id` | 字串 | 同一資料集內的車輛 ID | 非空白、無缺值；同一車須使用相同 ID |
| `time_s` | 實數 | 相對本資料集共同起點的秒數 | 有限、非負、無缺值 |
| `speed_smooth_mps` | 實數 | m/s | 已完成平滑；有限、非負、無缺值 |

補充約定：

- 一次呼叫只包含一個 ID 不衝突的資料集。多影片若重複使用車輛 ID，應先分開分析或建立不衝突的識別方式。
- `(vehicle_id, time_s)` 不可重複。原始 DataFrame 的列索引可以重複，函式不依賴它。
- 輸入可以未排序，允許其他欄位；其他欄位不參與計算，也不會自動出現在輸出。
- 數字字串，例如 `"12.5"`，應由資料轉換端先轉成數值；核心函式不默默猜測型別。
- 本例不要求時間等距，因為只取最大值；速度平滑所需的取樣規則，由平滑功能另外定義。
- 單位與平滑方法無法只靠數值可靠辨認。整合端須依來源規格轉換，並保留平滑參數與資料來源紀錄。

### 輸入參數

| 參數 | 型別 | 規則 |
| --- | --- | --- |
| `threshold_mps` | 實數 | 必填、有限、非負；單位 m/s，不接受布林值或字串 |

不提供預設速限，避免呼叫端忘記設定時，套件自行套用錯誤門檻。

### 判定與輸出

1. 找出每台車最高的 `speed_smooth_mps`。
2. 最高速度有多筆時，取 `time_s` 最早的一筆。
3. 僅保留最高速度 **嚴格大於 `threshold_mps`** 的車輛。
4. 依 `time_s`、`vehicle_id` 排序；ID 採字串排序。

輸出是 DataFrame，一列代表「這台車在本次傳入範圍內符合超速條件的代表資料」，不是每一段連續超速行為。

| 輸出欄位 | 型別 | 意義 |
| --- | --- | --- |
| `vehicle_id` | pandas `string` | 符合條件的車輛 ID |
| `time_s` | `float64` | 最高平滑速度對應的時間 |
| `peak_speed_mps` | `float64` | 該車最高平滑速度 |
| `threshold_mps` | `float64` | 本次實際採用的門檻 |

### 邊界情況

| 情況 | 本例行為 |
| --- | --- |
| 速度剛好等於門檻 | 不產生結果 |
| 輸入有必要欄位但沒有資料列 | 回傳固定欄位、固定型別的空表 |
| 沒有符合條件的車輛 | 回傳相同格式的空表 |
| 缺必要欄位、重複樣本、無效值 | 拋出 `ValueError`，提供原因 |
| 傳入的不是 DataFrame | 拋出 `TypeError` |
| 函式執行完成 | 不修改原始輸入、不自行讀寫檔案 |

以上是本教學採用的資料政策。未來若改成排除無效列，必須另外回報排除數量與原因，且更新規格與測試。

### 手算答案

門檻先使用 10 m/s，方便人工核對。這是測試數值，不代表任何路口法定速限。

| 車輛 | 時間（秒） | 平滑速度（m/s） | 預期結果 |
| --- | --- | --- | --- |
| A | 0、1、2 | 8、9、10 | 無，最高速度等於門檻 |
| B | 0、1、2 | 9、11、12 | 一筆：時間 2、速度 12 |
| C | 0、1、2 | 11、11、9 | 一筆：時間 0、速度 11 |

完成條件：先不看程式，就能從上述資料算出答案。若答案仍有爭議，先確認交通定義再寫算法。

## Step 3：建立一個最小 Python 套件

> **本專案已完成這一步，擴充功能時請跳過。** 以下保留給「從零建立另一個套件」時參考，
> 也說明現有骨架為什麼長這樣。本專案實際的 `pyproject.toml` 以檔案內容為準。

**本步產出：可安裝的專案結構。**

使用 Python 3.10 以上。以下指令的 `python` 必須指向你準備使用的 Python 3；Windows 也可使用對應的 `py -3` 建立環境。

先建立並進入專案資料夾：

```shell
mkdir traffickit
cd traffickit
python -m venv .venv
```

再依下表建立資料夾與檔案。後續步驟會給出各檔案內容；表內路徑都相對於專案根目錄。

| 檔案 | 用途 | 何時填寫 |
| --- | --- | --- |
| `README.md` | 套件使用說明（安裝、快速上手、功能索引） | 現在 |
| `docs/feature-development-guide.md` | 本教學與開發約定 | 現在 |
| `pyproject.toml` | 套件名稱、版本、相依套件、安裝設定 | 現在 |
| `src/traffickit/__init__.py` | 套件入口 | Step 4 |
| `src/traffickit/speed/__init__.py` | 公開的速度功能 | Step 4 |
| `src/traffickit/speed/_overspeed.py` | 判定的內部實作 | Step 4 |
| `examples/overspeed_demo.py` | 給其他工程師的呼叫範例 | Step 5 |
| `tests/test_overspeed.py` | 可重複執行的正確性檢查 | Step 6 |
| `docs/catalog.md` | 功能索引與指標對照 | Step 7 |
| `docs/worksheets/<功能 ID>.md` | 該功能的工作單與驗證紀錄 | Step 7 |

`pyproject.toml` 內容如下：

<!-- file: pyproject.toml -->
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "traffickit"
version = "0.1.0"
description = "Traffic analysis function development example"
readme = "README.md"
requires-python = ">=3.10"
dependencies = ["pandas>=2.2,<3.0"]

[tool.setuptools.packages.find]
where = ["src"]
include = ["traffickit*"]
```

本專案的安裝套件名稱與 Python `import` 名稱同為 `traffickit`。初期保留在同一個套件與程式庫內，新增功能不需要各自建立一個可部署服務。

此處的 Python 與 pandas 範圍是教學設定，正式交付前應依團隊驗證過的版本調整。套件描述相容範圍；部署環境則需要另外固定實際版本。

套件設定與 wheel 建置使用標準 Python 打包方式，可參考 [Python Packaging User Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)。

## Step 4：實作函式，公開介面只留一個入口

**本步產出：可直接接收資料並回傳結果的函式。**

先填入 `src/traffickit/__init__.py`：

<!-- file: src/traffickit/__init__.py -->
```python
"""交通分析套件。"""
```

填入 `src/traffickit/speed/__init__.py`：

<!-- file: src/traffickit/speed/__init__.py -->
```python
"""速度相關的公開功能。"""

from ._overspeed import detect_overspeed

__all__ = ["detect_overspeed"]
```

填入 `src/traffickit/speed/_overspeed.py`：

<!-- file: src/traffickit/speed/_overspeed.py -->
```python
from math import isfinite
from numbers import Real

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_complex_dtype,
    is_numeric_dtype,
)


_REQUIRED = ("vehicle_id", "time_s", "speed_smooth_mps")
_OUTPUT_DTYPES = {
    "vehicle_id": "string",
    "time_s": "float64",
    "peak_speed_mps": "float64",
    "threshold_mps": "float64",
}


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame({
        name: pd.Series(dtype=dtype)
        for name, dtype in _OUTPUT_DTYPES.items()
    })


def detect_overspeed(
    tracks: pd.DataFrame,
    *,
    threshold_mps: float,
) -> pd.DataFrame:
    """找出最高平滑速度嚴格超過門檻的車輛，每車回傳一列。

    Parameters
    ----------
    tracks : pandas.DataFrame
        單一資料集的樣本。必要欄位：vehicle_id（非空白字串）、
        time_s（共同起點的非負秒數）、speed_smooth_mps（非負 m/s）。
        數值須有限、無缺值；(vehicle_id, time_s) 不可重複。
        允許未排序或含額外欄位；不修改輸入。
    threshold_mps : float
        必填、有限且非負的速度門檻，單位 m/s。

    Returns
    -------
    pandas.DataFrame
        vehicle_id、time_s、peak_speed_mps、threshold_mps。
        同速取最早時間；按時間與字串 ID 排序；無結果時保留欄位型別。

    Raises
    ------
    TypeError
        tracks 不是 DataFrame。
    ValueError
        欄位、數值、ID、重複樣本或參數不符合輸入規格。

    Notes
    -----
    本函式不進行平滑、ROI 或時間裁切，也不讀寫檔案。
    每車一列代表本次資料範圍的超速判定，不是連續超速段落的數量。
    """
    if not isinstance(tracks, pd.DataFrame):
        raise TypeError("tracks 必須是 pandas.DataFrame")
    if (
        isinstance(threshold_mps, bool)
        or not isinstance(threshold_mps, Real)
        or not isfinite(threshold_mps)
        or threshold_mps < 0
    ):
        raise ValueError("threshold_mps 必須是有限、非負的實數（m/s）")
    if tracks.columns.duplicated().any():
        raise ValueError("輸入不可包含重複欄名")
    missing = sorted(set(_REQUIRED) - set(tracks.columns))
    if missing:
        raise ValueError(f"缺少必要欄位：{missing}")
    if tracks.empty:
        return _empty_result()

    # 複製必要欄位，避免修改呼叫端持有的原始資料。
    work = tracks.loc[:, list(_REQUIRED)].copy()
    valid_ids = work["vehicle_id"].map(
        lambda value: isinstance(value, str) and bool(value.strip())
    )
    if not valid_ids.all():
        raise ValueError("vehicle_id 必須是非空白字串且不可缺值")

    for column in ("time_s", "speed_smooth_mps"):
        values = work[column]
        if (
            not is_numeric_dtype(values.dtype)
            or is_bool_dtype(values.dtype)
            or is_complex_dtype(values.dtype)
        ):
            raise ValueError(f"{column} 必須是實數欄位，不接受數字字串")
        if values.isna().any():
            raise ValueError(f"{column} 不可有缺值")
        if not values.map(isfinite).all() or (values < 0).any():
            raise ValueError(f"{column} 必須是有限且非負的數值")
        work[column] = values.astype("float64")

    if work.duplicated(["vehicle_id", "time_s"]).any():
        raise ValueError("同一 vehicle_id 與 time_s 不可有重複樣本")
    work["vehicle_id"] = work["vehicle_id"].astype("string")

    # 先依時間排序。同速時，idxmax 選到該車最早的一筆。
    # 重設索引，避免原始列索引重複時 .loc 選出多筆資料。
    work = work.sort_values(
        ["vehicle_id", "time_s"], kind="stable"
    ).reset_index(drop=True)
    peak_indexes = work.groupby(
        "vehicle_id", sort=False
    )["speed_smooth_mps"].idxmax()
    peaks = work.loc[peak_indexes]
    selected = peaks.loc[
        peaks["speed_smooth_mps"] > threshold_mps
    ].copy()
    if selected.empty:
        return _empty_result()

    selected = selected.rename(
        columns={"speed_smooth_mps": "peak_speed_mps"}
    )
    selected["threshold_mps"] = float(threshold_mps)
    result = selected.loc[:, list(_OUTPUT_DTYPES)].astype(_OUTPUT_DTYPES)
    return result.sort_values(
        ["time_s", "vehicle_id"], kind="stable"
    ).reset_index(drop=True)
```

底線開頭的 `_overspeed.py` 是內部實作。其他工程師統一使用：

```python
from traffickit.speed import detect_overspeed
```

之後即使內部拆成多個檔案，這個公開匯入路徑仍可保持穩定。尚未被第二個功能需要的細節，先留在本檔案；等到兩個功能確實需要相同語意，再抽共用函式。

完成條件：程式中沒有客戶專屬路徑、GUI 狀態、HTTP 物件或存檔動作。輸入、輸出與錯誤符合 Step 2。

## Step 5：寫一個其他工程師可以直接跑的範例

**本步產出：`examples/overspeed_demo.py`。**

<!-- file: examples/overspeed_demo.py -->
```python
import pandas as pd

from traffickit.speed import detect_overspeed


def main() -> None:
    tracks = pd.DataFrame({
        "vehicle_id": ["A"] * 3 + ["B"] * 3 + ["C"] * 3,
        "time_s": [0.0, 1.0, 2.0] * 3,
        "speed_smooth_mps": [8, 9, 10, 9, 11, 12, 11, 11, 9],
    })
    events = detect_overspeed(tracks, threshold_mps=10.0)
    print(events.to_string(index=False))
    print(f"超速車輛數：{len(events)}")


if __name__ == "__main__":
    main()
```

先安裝開發中的套件，再執行範例。所有指令均在專案根目錄執行；直接指定虛擬環境的 Python，不需要先啟用環境。

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe examples/overspeed_demo.py
```

Linux／macOS：

```bash
./.venv/bin/python -m pip install -e .
./.venv/bin/python examples/overspeed_demo.py
```

`-e` 是開發用的可編輯安裝，修改原始碼後可重新執行範例。首次安裝需要能取得宣告的相依套件；公司內網環境由整合工程師提供套件來源。

預期資料內容如下，顯示空白可能依版本不同：

| vehicle_id | time_s | peak_speed_mps | threshold_mps |
| --- | --- | --- | --- |
| C | 0.0 | 11.0 | 10.0 |
| B | 2.0 | 12.0 | 10.0 |

預期印出「超速車輛數：2」。因為本功能明確約定每車一列，此處才能以 `len(events)` 計算車輛數；這個寫法不可直接套用到所有衝突事件表。

CSV 寫入可以由使用者在呼叫後自行處理，例如 `events.to_csv(...)`。它不需要放入 `detect_overspeed()`。

## Step 6：將手算答案變成可重複執行的測試

**本步產出：`tests/test_overspeed.py`。**

使用 Python 內建 `unittest`，本教學不需要額外安裝測試框架。測試驗證規格中的交通邊界與資料品質，不重寫一遍算法當作預期答案。

<!-- file: tests/test_overspeed.py -->
```python
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from traffickit.speed import detect_overspeed


class TestDetectOverspeed(unittest.TestCase):
    def setUp(self):
        self.tracks = pd.DataFrame({
            "vehicle_id": ["A"] * 3 + ["B"] * 3 + ["C"] * 3,
            "time_s": [0.0, 1.0, 2.0] * 3,
            "speed_smooth_mps": [8, 9, 10, 9, 11, 12, 11, 11, 9],
        })

    def test_expected_vehicles_times_and_units(self):
        actual = detect_overspeed(self.tracks, threshold_mps=10.0)
        expected = pd.DataFrame({
            "vehicle_id": pd.Series(["C", "B"], dtype="string"),
            "time_s": [0.0, 2.0],
            "peak_speed_mps": [11.0, 12.0],
            "threshold_mps": [10.0, 10.0],
        })
        assert_frame_equal(actual, expected)

    def test_unsorted_rows_duplicate_index_and_no_mutation(self):
        shuffled = self.tracks.sample(frac=1, random_state=7).copy()
        shuffled.index = [0] * len(shuffled)
        before = shuffled.copy(deep=True)
        actual = detect_overspeed(shuffled, threshold_mps=10.0)
        expected = detect_overspeed(self.tracks, threshold_mps=10.0)
        assert_frame_equal(actual, expected)
        assert_frame_equal(shuffled, before)

    def test_empty_and_no_matches_have_same_schema(self):
        from_empty = detect_overspeed(
            self.tracks.iloc[:0], threshold_mps=10.0
        )
        from_no_matches = detect_overspeed(
            self.tracks, threshold_mps=100.0
        )
        assert_frame_equal(from_empty, from_no_matches)
        self.assertEqual(list(from_empty.columns), [
            "vehicle_id", "time_s", "peak_speed_mps", "threshold_mps"
        ])
        self.assertEqual(
            [str(dtype) for dtype in from_empty.dtypes],
            ["string", "float64", "float64", "float64"],
        )

    def test_missing_column_is_reported(self):
        invalid = self.tracks.drop(columns="speed_smooth_mps")
        with self.assertRaisesRegex(ValueError, "缺少必要欄位"):
            detect_overspeed(invalid, threshold_mps=10.0)

    def test_bad_speed_values_are_rejected(self):
        for value in [float("nan"), float("inf"), -1.0]:
            with self.subTest(value=value):
                invalid = self.tracks.astype({"speed_smooth_mps": "float64"})
                invalid.loc[0, "speed_smooth_mps"] = value
                with self.assertRaisesRegex(ValueError, "speed_smooth_mps"):
                    detect_overspeed(invalid, threshold_mps=10.0)
        invalid = self.tracks.astype({"speed_smooth_mps": "string"})
        with self.assertRaisesRegex(ValueError, "speed_smooth_mps"):
            detect_overspeed(invalid, threshold_mps=10.0)

    def test_duplicate_sample_is_rejected(self):
        invalid = pd.concat([self.tracks, self.tracks.iloc[[0]]])
        with self.assertRaisesRegex(ValueError, "重複樣本"):
            detect_overspeed(invalid, threshold_mps=10.0)

    def test_invalid_parameters_are_rejected(self):
        for value in [True, "10", -1, float("nan"), float("inf")]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "threshold_mps"):
                    detect_overspeed(self.tracks, threshold_mps=value)

    def test_invalid_id_and_time_are_rejected(self):
        for column, value in [("vehicle_id", "  "), ("time_s", -1.0)]:
            with self.subTest(column=column):
                invalid = self.tracks.copy()
                invalid.loc[0, column] = value
                with self.assertRaisesRegex(ValueError, column):
                    detect_overspeed(invalid, threshold_mps=10.0)


if __name__ == "__main__":
    unittest.main()
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux／macOS：

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

完成條件：顯示 `Ran 8 tests` 與 `OK`。

**要接回舊程式時，再補一份真實資料回歸比較。** 使用相同資料、平滑結果、門檻及分析範圍，比較新舊輸出的車輛 ID、代表時間與速度。若改變同速選取、錯誤處理或其他規則，將差異列出並確認，不要把「與舊版相同」當成交通定義必然正確的證據。

## Step 7：登記功能，讓上百個功能仍找得到

**本步產出：`docs/catalog.md` 的第一筆功能紀錄。**

先維護一份簡單索引。詳細 I/O 以函式旁的 docstring 為準，範例與測試提供可執行的證據。新增功能時一併更新，功能變多後可由 docstring 自動產生分類文件。

> **本專案的 `docs/catalog.md` 已存在**，擴充時是「新增一列」而不是重建檔案。
> 下列內容示範最初的樣子；實際的欄位定義、狀態升級條件與契約版規則以
> [`docs/catalog.md`](catalog.md) 開頭的說明為準。

將下列內容存成 `docs/catalog.md`：

<!-- file: docs/catalog.md -->
```markdown
# 交通功能目錄

| 功能 ID | 公開入口 | 用途 | 負責人 | 契約版 | 狀態 |
| --- | --- | --- | --- | --- | --- |
| speed.detect_overspeed | traffickit.speed.detect_overspeed | 每車最高平滑速度超過門檻 | 交付前填入姓名 | 1 | 試行 |

## speed.detect_overspeed

- 必要資料：vehicle_id、time_s、speed_smooth_mps。
- 參數：threshold_mps，有限、非負，單位 m/s。
- 輸出粒度：每台符合條件的車一列；同速取最早時間。
- 詳細規格：函式 docstring、README 的 Step 2。
- 原始碼：src/traffickit/speed/_overspeed.py。
- 範例：examples/overspeed_demo.py。
- 測試：tests/test_overspeed.py。
- 前置條件：完成平滑；資料集內 ID 唯一；分析範圍由呼叫端決定。
- 限制：不輸出連續超速段落，不推定道路法定速限。

## 指標與計算能力對照（後續整合用，尚未實作情境入口）

| 指標 ID | 使用功能 | 情境端提供的參數 |
| --- | --- | --- |
| UNSIG_V_3 | speed.detect_overspeed | 路口設定速限，由 km/h 換算成 m/s |
| UNSIG_V_4 | speed.detect_overspeed | 路口設定速限加 10 km/h，再換算成 m/s |

加 10 km/h 來自既有程式設定，不在此認定為法規要求。
情境入口仍需負責指標適用性、方向範圍與統計方式。
```

「功能」與「指標」分開登記：V3、V4 可以共用一個算法，只使用不同參數。負責人、契約版與狀態用來協作；套件版本仍以 `pyproject.toml` 為準。改變輸入、輸出或計算語意時，更新契約紀錄、範例與測試。

三個欄位的填法：

- **負責人**：填實際能回答交通定義問題的人，不填「待補」。新增功能時由提出需求的人指定。
- **契約版**：從 1 開始。改變輸入欄位、輸出欄位、判定規則或統計口徑時 +1，並在 catalog 記錄差異。
  只改內部實作、效能或錯誤訊息措辭時不動。
- **狀態**：草擬／試行／正式／淘汰四階段，升級條件見 [`docs/catalog.md`](catalog.md) 的「狀態定義」。

除了 catalog 的一列，每個功能還要有一份工作單 `docs/worksheets/<功能 ID>.md`，
內容就是本教學最後「每個新功能都要填的一張工作單」那份格式，加上驗證紀錄。

完成條件：沒參與開發的人，能從目錄找到功能入口、I/O、負責人與可執行範例。

## Step 8：打包交付，驗證安裝後能用

**本步產出：wheel 安裝檔，以及一份可重現的交付紀錄。**

正式交付使用安裝檔；開發環境中的 `-e` 安裝用於開發迭代。以下只建立本機安裝檔，不涉及發布到公開套件平台。

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip wheel --no-deps . --wheel-dir dist
```

Linux／macOS：

```bash
./.venv/bin/python -m pip wheel --no-deps . --wheel-dir dist
```

`--no-deps` 表示本次只建置此專案的 wheel；pandas 等執行相依套件仍需在安裝環境中取得。此純 Python 範例的安裝檔預期為：

`dist/traffickit-0.1.0-py3-none-any.whl`

接著建立另一個驗收環境，從 wheel 安裝，再執行相同範例及測試，以發現「只有原始碼目錄裡才跑得動」的問題。

Windows PowerShell：

```powershell
python -m venv .venv-check
.\.venv-check\Scripts\python.exe -m pip install dist/traffickit-0.1.0-py3-none-any.whl
.\.venv-check\Scripts\python.exe examples/overspeed_demo.py
.\.venv-check\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-check\Scripts\python.exe -m pip freeze > requirements-validated.txt
```

Linux／macOS：

```bash
python -m venv .venv-check
./.venv-check/bin/python -m pip install dist/traffickit-0.1.0-py3-none-any.whl
./.venv-check/bin/python examples/overspeed_demo.py
./.venv-check/bin/python -m unittest discover -s tests -v
./.venv-check/bin/python -m pip freeze > requirements-validated.txt
```

`requirements-validated.txt` 用來記錄這次實際安裝的套件版本。從本機 wheel 安裝的套件可能記成含本機路徑的參照，所以這份紀錄不是可直接搬到所有主機的部署鎖檔。整合工程師應搭配該 wheel、部署平台與可取得的相依套件，整理可重建的安裝來源。離線主機也需要對應作業系統與 Python 版本的相依套件安裝檔。

交付紀錄至少包含：

| 項目 | 要填寫的內容 |
| --- | --- |
| 版本 | 套件版本、Git commit 或標籤 |
| 驗證環境 | OS、Python、pandas 等實際版本 |
| 驗證結果 | 8 個教學測試是否通過、真實資料比較結果 |
| 效能 | 真實資料列數、車輛數、執行時間及測試主機 |
| 行為變更 | 與上一版相比，哪些輸入或結果可能不同 |
| 限制 | 本次僅支援批次資料、尚未驗證的平台或資料情況 |

效能只需先記錄一份具代表性的資料，作為後端估算任務時間的依據。教學用三台車不能代表實際路口的大量資料效能。

完成條件：驗收環境從 wheel 安裝後，範例與測試均成功；另一位工程師能依紀錄重現使用方式。

## 第一個功能完成後，下一個功能怎麼加？

每次只新增一項能力，重複 Step 1、2、4、5、6、7、8。套件骨架已存在，不必為每個功能重建。

| 新需求 | 程式放在哪裡 | 需要先決定的事 |
| --- | --- | --- |
| 速度平滑 | `traffickit.speed` 的新函式 | 窗口代表樣本數或秒數、邊界、缺值、取樣間隔 |
| 車速分布 | ~~新函式~~ **已完成**：`traffickit.speed.summarise_speed_distribution` | 每車或每樣本權重、分箱邊界、分母、時間與車種篩選 |
| 轉向流量 | ~~新函式~~ **已完成**：`traffickit.volume.summarise_turn_volume` | 轉向類別由誰判定、合法轉向清單、PCU 權重來源、未分組車種 |
| 連續超速段落 | 另一個公開函式 | 起訖時間、可容忍中斷、同車多段如何編號 |
| 非號誌整體分析 | 未來的 `traffickit.scenarios` | 適用指標、前置運算、判定組合、彙整口徑 |
| CSV 輸出、網頁表格 | 應用端 | 欄位順序、顯示單位、下載與存放位置 |

本例第一版回傳 DataFrame 就足夠；不必先讓所有未來函式都回傳同一種大型物件。共同的是清楚的契約與資料語意，而不是強迫所有功能擁有一模一樣的參數。

### 篩選與圖表的分工

| 使用者操作 | 交通功能工程師定義 | 應用端處理 |
| --- | --- | --- |
| 看某個時段的每車最高速度 | 先切時段再取最大值，時間區間端點如何包含 | 提供起訖時間並呼叫功能 |
| 只看已產生事件中的某個時段 | 事件代表時間的意義 | 篩選結果表並重新呈現 |
| 看機車與汽車的速度分布 | 每車或每樣本、分箱、分母 | 車種選單、圖表與互動 |
| 看涉及機車的衝突 | 主體／關聯車角色及篩選規則 | 將篩選要求傳入或套用到結果 |

先取全時段最高速度再篩選代表時間，與先切時段再計算最高速度，答案可能不同。互動設計前先確認使用者要哪一種。

衝突分析還需要保留關聯車：不能為了只看機車事件，就在計算前刪除所有汽車軌跡。平滑或衝突時間窗需要的前後資料，也應由交通功能規格說明保留方式。

### 很多指標與事件的情境如何沿用？

當要整合非號誌、機會左轉或人車衝突，再增加「情境入口」來組合已驗證的功能。情境入口及它的交通依賴關係，仍由交通功能工程師維護。

| 層次 | 例子 | 責任 |
| --- | --- | --- |
| 計算功能 | 超速、穿越時間、間隙 | 可獨立驗證的計算與資料結果 |
| 指標規格 | V3、V4 | 門檻、適用條件、依賴、統計口徑 |
| 情境入口 | 非號誌分析 | 安排前置處理與功能呼叫，整理情境結果 |

例如既有左轉程式的 C3 依賴 R5 找出的減速車輛。未來可以共享明確的減速車輛結果；只要求輸出 C3 時，仍要執行必要的前置判定。依賴關係放在情境程式與規格中，第一版用明確的 Python 呼叫即可。

情境結果擴大時，再視需要分成事件、連續量測、摘要與指標狀態。須區分「成功計算且零事件」「不適用」「缺資料」「執行失敗」。也要保留未發生事件的分析對象或其總數，否則不能只靠事件表重建分母。

### 網頁、API、桌面程式怎麼使用？

| 使用方式 | 整合流程 |
| --- | --- |
| 網頁 | 後端讀取與轉換資料 → 呼叫套件 → 將結果轉成 JSON → 前端呈現 |
| 對外 API | API 層驗證請求與權限 → 呼叫套件 → 回傳結果或任務識別碼 |
| Python 桌面程式 | 安裝套件 → 背景執行計算 → 將結果交給 GUI 顯示 |
| 客戶主機的批次程式 | 安裝固定版本 → 讀入檔案 → 呼叫套件 → 儲存結果 |

這裡的公開函式介面是 Python API；對外 HTTP API 由後端另外包裝。非 Python 桌面程式可透過 HTTP 或另外的整合方式使用，不能直接把 Python 套件當成原生函式庫匯入。資料量大時由應用端安排背景工作，避免阻塞網頁請求或 GUI。

## 每個新功能都要填的一張工作單

可直接複製以下格式：

```markdown
- 功能 ID：
- 一句目的：
- 主要負責人：
- 公開函式入口：
- 必要輸入：欄位、型別、單位、時間／座標基準。
- 參數：意義、單位、範圍、預設值。
- 輸出：一列／一筆代表什麼、欄位、型別、排序。
- 判定規則：比較方式、邊界與同值處理。
- 前置條件：平滑、校正、其他功能或情境資料。
- 品質政策：缺值、重複、異常、空資料如何處理。
- 統計口徑：計數對象、分母、時間範圍；不適用請註明。
- 手算範例：至少一個成立、一個不成立、一個邊界案例。
- 原始碼／範例／測試位置：
- 驗證環境與版本：
- 舊程式差異與已知限制：
```

## 交付前確認

- [ ] 公開入口、必要欄位、單位與輸出粒度已寫清楚。
- [ ] 函式不修改輸入，不依賴 UI、HTTP、客戶路徑或檔案寫入。
- [ ] 手算案例、門檻邊界、空結果與主要資料錯誤已驗證。
- [ ] 其他工程師可直接執行範例，功能目錄已有負責人。
- [ ] 從 wheel 安裝後可呼叫；版本與實際驗證環境有紀錄。
- [ ] 若替換既有算法，已比較同一份真實資料並說明差異。

**每一次交辦都到這裡為止：完成該功能的八個步驟。這份交付通過後，再用同一格式新增下一個交通功能。**

## 附錄：本教學範例程式的驗證紀錄

以下是**教學範例 `detect_overspeed`** 的驗證紀錄，不是 TrafficKit 本身的交付紀錄。
各功能實際的驗證紀錄寫在自己的工作單，例如
[`docs/worksheets/speed.speed_distribution.md`](worksheets/speed.speed_distribution.md)。

本文件內標記檔名的程式區塊已抽出成暫存專案，於 2026-09-09 完成以下驗證：

| 項目 | 結果 |
| --- | --- |
| 執行環境 | Linux、Python 3.12.14、pandas 2.2.3、setuptools 84.0.0 |
| 可編輯安裝與範例 | 成功；回傳 C、B 兩台車，時間及速度與手算一致 |
| 規格測試 | 8 個測試全部通過 |
| wheel 建置 | 成功產生 `traffickit-0.1.0-py3-none-any.whl` |
| 另一個虛擬環境安裝 wheel | 成功；確認匯入已安裝版本，再次通過範例與 8 個測試 |

這次驗證重用環境既有的相依套件，以離線方式安裝及建置；沒有驗證從網路下載所有依賴的流程。Windows 指令、其他 Python／pandas 版本、實際大量資料效能與四個既有情境程式的完整整合，仍需在團隊環境驗收。本範例沒有更動原有程式。
