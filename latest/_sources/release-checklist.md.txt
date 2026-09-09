# 發行與文件更新檢查表

## 每次新增或修改功能都要做（不必發行）

1. 更新 docstring——**API reference 完全由 docstring 產生**，改了程式沒改
   docstring，網站就會是錯的。
2. 新功能要在 `docs/api/<子套件>.rst` 的 `autosummary` 加上名稱，
   否則不會出現在網站上。新增子套件時另外建一頁並加進 `docs/api/index.rst`
   的 `toctree`。
3. 在 `docs/catalog.md` 新增或修改該功能那一列。
4. 新增或更新 `docs/worksheets/<功能 ID>.md`，並加進
   `docs/worksheets/index.md` 的 `toctree`。
5. 契約有變（輸入、輸出、判定規則、統計口徑）→ 契約版 +1，
   並在 `docs/catalog.md` 的「契約變更紀錄」列出差異。
6. 本機建置一次，確認沒有新的警告：

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -e ".[docs]"
   .\.venv\Scripts\python.exe -m sphinx -b html -W --keep-going docs docs\_build\html
   ```

   `-W` 會把警告當成錯誤。名稱拼錯、`toctree` 漏掉頁面、交叉參照失效都會在
   這一步被抓出來。

推上 `master` 後，GitHub Actions 會把網站更新到
<https://yckao5888.github.io/TrafficKit/latest/>。

## 要發行一個版本時

1. 確認要發行的功能狀態正確（草擬／試行／正式，見
   [功能目錄](catalog.md#狀態)）。**沒做真實資料回歸比較就不可以寫「正式」。**
2. 改 `pyproject.toml` 的 `version`。
3. 在 `docs/switcher.json` **最前面**加一筆新版本：

   ```json
   {
     "name": "0.2.0",
     "version": "0.2.0",
     "url": "https://yckao5888.github.io/TrafficKit/0.2.0/"
   }
   ```

   這一份是版本切換器的唯一來源，漏加的話新版文件上線但選單裡看不到。
4. 更新各功能工作單的「驗證環境與版本」表。
5. 提交後打 tag 並推上去：

   ```powershell
   git tag v0.2.0
   git push github master --tags
   ```

   tag 觸發的建置會把文件放到 `/0.2.0/`，**發佈後就不再變動**；
   `/latest/` 仍然跟著 master 走。

## 網站結構

```
yckao5888.github.io/TrafficKit/
├─ index.html      轉址到 latest/
├─ switcher.json   版本選單的來源（所有版本共用根目錄這一份）
├─ latest/         master 每次 push 更新
├─ 0.1.0/          tag v0.1.0 當下的快照
└─ 0.2.0/
```

## 第一次啟用 GitHub Pages（只做一次）

1. GitHub → repo → **Settings → Pages**。
2. **Source** 選 **Deploy from a branch**，branch 選 `gh-pages`、資料夾 `/ (root)`。
3. 若 `gh-pages` 分支還不存在，先推一次 `master` 讓 Actions 建立它，
   再回來設定。
4. Settings → Actions → General → **Workflow permissions** 要是
   **Read and write permissions**，Actions 才能推 `gh-pages`。
