# TrafficKit 文件

交通分析計算套件。提供可安裝、可呼叫、可驗證的交通計算功能。

網頁後端、Python 桌面程式與批次工具安裝同一份套件，呼叫相同函式。
**套件只負責計算**：資料讀取、單位換算來源、圖表與檔案輸出由呼叫端負責，
唯一的例外是 `traffickit.formats` 格式轉換層。

```{toctree}
:maxdepth: 2
:hidden:

api/index
catalog
worksheets/index
開發指南 <feature-development-guide>
feature-request-template
release-checklist
```

## 從這裡開始

[API reference](api/index)
: 每個公開函式的參數、回傳、例外與注意事項，由程式碼的 docstring 產生。

[功能目錄](catalog)
: 功能索引、狀態定義、契約版規則，以及與舊程式的差異對照。

[工作單](worksheets/index)
: 每個功能的完整契約、手算範例與實跑的驗證紀錄。

[開發指南](feature-development-guide)
: 新增一個交通功能的八個步驟與交付格式。

## 安裝

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

需求：Python ≥ 3.10、pandas 2.2–3.0、numpy ≥ 1.26。

## 使用前必讀的四個約定

1. **單位一律 m/s、時間一律「相對本資料集共同起點的秒數」。**
   像素／公尺比例尺換算、km/h 顯示是呼叫端的責任。
2. **輸入不乾淨就拋錯，不默默丟資料。** 缺欄位、缺值、負值、重複樣本一律
   `ValueError`；傳錯型別是 `TypeError`。函式不修改傳入的 DataFrame。
3. **統計對象是「車」還是「樣本」由各功能明訂。** 分母怎麼算、範圍外的資料
   算不算，都寫在該功能的工作單裡，不要用猜的。
4. **計算功能不碰檔案。** 只有 `traffickit.formats` 會讀檔，而且它只做
   欄位與型別轉換，不做交通判定。

## 版本

本頁對應的版本顯示在標題列與右上角的版本選單。每個發行版的文件在發佈後
就不再變動，客戶裝哪一版就查哪一版；`latest` 追蹤 master 的最新狀態。
