# Codex Quota

Windows 的 Codex 專用用量橫條。Python 3 標準函式庫，無需 pip。
依照 ccquota 的簡潔橫條外觀製作，只讀 Codex 資料。

雙擊 `Start.bat` 啟動；也可執行 `python codex_quota.py`。
預設跟隨前景 Codex / ChatGPT 桌面視窗，在底部輸入區上方置中顯示（橫條下緣距視窗底部 135px）。
輸入框高度會隨內容與縮放變動，可拖曳微調；調整後會保存距視窗底部的距離。
這是獨立懸浮視窗，並非官方原生 UI 擴充，不會為對話內容預留版面。
首次未偵測到 Codex 時會保持獨立顯示；切回 Codex 後開始跟隨。
偵測到目標後，切換到其他 App 或最小化目標會隱藏。

- 拖曳橫條調整位置，跟隨模式儲存相對位置。
- 右鍵可切換跟隨、立即更新、重設位置或結束。
- `Esc` 結束。`python codex_quota.py --detached` 可獨立顯示。
- 不修改 Codex 安裝檔、啟動設定或全域設定，不加入開機啟動。

## 數字與來源

- **5h / 週**：已使用的額度百分比，含各自重置倒數。
  每 60 秒透過本機 `codex.exe app-server` 的 `account/rateLimits/read` 讀取。
  使用既有 Codex 登入；不讀取或輸出憑證，不送出模型請求。
  失敗時讀取 `.codex/sessions` 及 `.codex/archived_sessions` 裡的 token_count 事件。
  綠色圓點代表即時查詢，黃色代表本機紀錄或額度不可用；已過重置時間的額度顯示 `—`。
- **今日**：系統本地時區今天的 Codex Token；每 15 秒更新。
  以每個紀錄檔累計 token counter 的增量相加，重複 counter 不重算。
  input 已包含 cached input，output 已包含 reasoning，不另外重複加入。
  不同分支若各自重播了相同的歷史用量，可能重複計入；缺失的紀錄無法補算。
  首次掃描所有紀錄，之後只讀新增內容；不儲存對話文字。
- **顏色**：已用 <70% 綠、70–89% 黃、≥90% 紅。
- 不顯示 Claude Code 用量、程序數、估算費用或無法對應目前對話的 context。
  訂閱額度百分比與 Token 總量是不同度量，不能直接換算。

`CODEX_HOME` 可指定紀錄來源，`CODEX_CLI_PATH` 可指定原生 `codex.exe`。
預設尋找 `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe`。
`python codex_quota.py --json` 可輸出純數字供診斷。

app-server 讀取沿用上一層的 `ccquota.py`，所以要放在 ccquota repo 裡執行。
