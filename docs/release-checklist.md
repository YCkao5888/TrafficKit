# 發行與文件更新檢查表

## 每次新增或修改功能都要做（不必發行）

完整清單在 repo 根目錄的
[`CLAUDE.md`](https://github.com/YCkao5888/TrafficKit/blob/master/CLAUDE.md)
——「依下列清單交付」的九項表格，以及「改了什麼 → 要更新哪些檔案」對照表。
**那裡是唯一來源**，本檔不重抄，只提醒與文件網站直接相關的三件事：

1. **改程式一定要改 docstring。** API reference 完全由 docstring 產生，
   程式改了 docstring 沒改，網站上就是錯的。
2. **新名稱要登記進 `autosummary`。** 寫好 docstring 不等於會出現在網站上；
   沒加進 `docs/api/<子套件>.rst` 的清單就不會被產生。
3. **契約有變就升契約版**（輸入、輸出、判定規則、統計口徑），
   並在 `docs/catalog.md` 的「契約變更紀錄」列出差異與對呼叫端的影響。

然後本機建置一次，確認沒有新的警告：

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -e ".[docs]"
   .\.venv\Scripts\python.exe -m sphinx -b html -W --keep-going -d docs\_build\doctrees docs docs\_build\html
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

   **`"preferred": true` 固定留在 `latest` 那一筆，不要跟著新版本搬。**
   它是版本警告橫幅的基準：掛在 `latest` 時，舊版頁面才會顯示「你看的
   不是最新版」。掛到某個版號上會反過來——在 `latest` 顯示警告，把讀者
   導去舊快照。站台根目錄的 `index.html` 一律轉址到 `latest/`。
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
