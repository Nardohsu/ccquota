# ccquota：Claude Code + Codex 額度監控

[← 回 README](../README.zh-Hant.md)

分享一個我自己用 Claude 做的小工具 **ccquota**。

## 為什麼做

平常用 Claude Code 和 Codex 寫程式，常常要確認 5 小時和每週額度用了多少、什麼時候重置。

同時開好幾個 Session 工作時，我也想知道現在的 Context、Token、Cache 命中率，以及到底有幾個 Session 在跑。

所以我用 Claude 做了一個 Python 小工具 **ccquota**，把這些資訊直接顯示在 Claude Code 裡，另外還做了一個像素風的獨立儀表板。後來也幫 Codex 桌面版做了一條額度橫條。

## 我是怎麼做的

一開始要解決的不是介面，而是「額度資料到底要去哪裡拿」。

最後整理出三種資料來源：

- **Claude Code 官方數字**：Status Line 每次執行時收到的 JSON，以及 Mod 從執行環境讀到的資料，裡面有官方額度、Context、Cache 等資訊。
- **本機使用紀錄**：用 Python 解析 Claude Code 本來就會寫在電腦上的對話紀錄，統計 Token、請求數和 Session 狀態。
- **Codex 本機服務**：向 Codex 的 app-server 查詢即時額度，查不到時才退回讀本機紀錄。

再把這些資料接到四種顯示方式：Claude Code 的 Mod、Status Line、像素風面板，以及 Codex 桌面版的懸浮橫條。

Codex 桌面版的橫條是交給 Codex 做的，我負責檢查它會不會動到 Claude Code，再整合進同一個專案。查額度的部分直接沿用 ccquota 原本的程式，不另外維護一份。

整個工具只用 Python 標準函式庫，不用另外安裝第三方套件。

## 開發過程中踩到的坑

這部分比做介面學到的還多。

### 1. 讀得到資料，不代表是最新的

Claude Code 會在本機存一份額度快取，但實測更新時間完全不固定，曾經八天都沒更新。

Codex 也一樣：本機紀錄寫著每週用了 13%，即時查詢的結果其實已經是 47%。

所以不能把讀到的數字直接當成即時額度。後來改成優先用官方即時數字，拿不到才退回快取或本機紀錄，而且畫面上會標明哪些是估算值。

### 2. Token 不能直接全部加起來

同一個 API 回應，在對話紀錄裡常常會出現好幾筆。

直接加總的話，實測一週會多算 136%。

後來改用 Message ID 加 Request ID 去除重複，也把 Cache Read Token 分開算，避免把每一輪重讀的 Context 當成新的消耗。

### 3. Session 檔案還在，不代表程式還在跑

Session 被強制關掉時，紀錄檔不會跟著刪掉。

所以不能只數檔案，要再問作業系統這個 Process ID 是不是還活著。

### 4. 能跑，不代表適合一直跑

原本每次更新都把紀錄從頭讀一遍，資料一多就變慢。

後來改成增量快取，只解析新增的部分。

在約 326 MB 的紀錄上，讀取時間從約 0.6 秒降到 0.04 秒。

### 5. 自己電腦能用，不代表別人裝了也能用

做成 Claude Code 的 Mod 之後，我才發現從 marketplace 安裝時，只會複製 Mod 所在的那個資料夾。原本的寫法下，負責統計的 Python 腳本根本沒有被裝進去，預設路徑也寫死成我自己電腦上的位置。

在我自己的電腦上一切正常，換成別人安裝就會少掉一半的資訊。後來調整了專案結構，安裝時會把腳本一起帶上，也會自動找到它的位置。

### 6. 沒有開放擴充，就只能「貼」上去

Claude Code 有 Mod 機制，橫條可以直接長在輸入框上方。Codex 桌面版沒有開放這種擴充，沒辦法把介面嵌進 App 裡。

最後的做法是做一個置頂的小視窗，偵測 Codex 視窗的位置，跟著它停在輸入框上方；切到其他 App 或把 Codex 縮小時就自動隱藏。看起來像內建的，其實是兩個獨立的視窗。

## 這次學到什麼

最大的收穫是：

**AI 可以幫忙很快把程式寫出來，但資料來源可不可靠、統計邏輯對不對，還是要自己驗證。**

尤其是用量監控工具，畫面漂亮不代表數字正確。

我覺得有三件事特別重要：

- 搞清楚每個數字是官方即時值、快取，還是估算值
- 先確認資料有沒有重複，不要看到 Token 就直接相加
- 不要為了即時更新，一直重複讀大量檔案

這些觀念應該也適用在其他監控工具或 Log 分析程式。

## 目前能做什麼

- 同時顯示 Claude Code 和 Codex 的 5 小時、每週額度與重置時間
- 顯示 Context、Cache 命中率、今日 Token、花費和執行中的 Session 數量
- 額度用到 70% 變黃色、90% 變紅色
- Mod 模式：在 Claude Code 桌面版和 CLI 的輸入框上方顯示一條資訊列
- CLI Status Line
- 獨立的像素風面板，把額度監控變成冒險公會儀表板
- Codex 桌面版橫條：跟著 Codex 視窗停在輸入框上方，顯示 Codex 的 5 小時、每週額度、重置倒數和今日 Token，可拖曳調整位置

## 怎麼用

需要 Python 3.7 以上。

在 Claude Code 裡顯示（推薦，桌面版也能用）：在終端機的 `claude` 裡輸入

```
/plugin install ccquota --marketplace Nardohsu/ccquota
```

想用像素風面板或 Codex 桌面版橫條，就從 GitHub 下載：

```bash
git clone https://github.com/Nardohsu/ccquota.git
cd ccquota
python ccquota_panel.py
```

Windows 也可以直接雙擊 `panel.bat` 開面板。

Codex 桌面版橫條（目前只支援 Windows）：雙擊 `codex-overlay/Start.bat`，再切回 Codex 就會看到。拖曳可以移動位置，右鍵有選項，按 `Esc` 關閉。

面板讀的 Claude 官方額度來自 Status Line，建議搭配 CLI 的 Status Line 一起用，不然官方額度可能會顯示「—」。Status Line 的設定方式請看 [README](../README.zh-Hant.md)。

## 其他

這個工具不需要 API Key，也不會讀取對話內容，只解析 Token 數和時間。

Claude 的部分完全在本機處理。Codex 的額度則是啟動你電腦上的 Codex，由它用自己的登入向 OpenAI 查詢，ccquota 不會讀取或保存你的登入資料。

Codex 橫條不會修改 Codex 的安裝檔或設定，也不會加入開機啟動，不想用了直接關掉就好。

目前的限制：

- Codex 額度用的是實驗性介面，之後可能要跟著 Codex 版本調整
- Codex 桌面版的橫條是懸浮視窗，不是真正嵌在 App 裡，Codex 的版面也不會為它留空間

我自己會繼續使用和修改，程式碼也公開給有需要的人參考。

採用 MIT License，免費開源。

有在用 Claude Code 或 Codex 的話，歡迎試試看。

遇到 Bug、想到更好的做法，或對這類額度監控工具有什麼建議，都歡迎到 [Issues](https://github.com/Nardohsu/ccquota/issues) 一起討論！
