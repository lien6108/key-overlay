# Key Overlay

在螢幕左下角即時顯示目前按下的按鍵；同時按住的鍵以 `+` 相連，例如 `Ctrl + Shift + Z`。適合錄影、教學、簡報示範快捷鍵。

```
┌──────────────────────────────┐
│ [Ctrl] + [Shift] + [Z]       │   ← 主螢幕左下角（工作列上方）
└──────────────────────────────┘
```

- 純 Python 標準函式庫（`ctypes` 掛 `WH_KEYBOARD_LL` 全域 hook + `tkinter`），零第三方依賴
- 置頂、滑鼠可穿透、不搶焦點、不出現在工作列
- 啟動時跳出設定視窗：確認是否開始、挑顯示顏色（亮黃／亮藍／亮白，附實際效果預覽）、提示關閉方式；選擇會記在 `%APPDATA%\KeyOverlay\settings.json`
- 只顯示當下一筆組合；所有鍵放開後停留 1.5 秒再淡出
- 修飾鍵固定排序 `Win → Ctrl → Alt → Shift`，左右 Ctrl/Shift/Alt 合併顯示
- 右下角通知區域有黃色 K 圖示，按右鍵 →「結束 Key Overlay」即可關閉
- 單一實例：重複開啟不會出現第二個
- 低資源：事件驅動（沒按鍵時 UI 執行緒完全休眠，不輪詢），實測閒置 CPU 約 0%、獨占記憶體約 20 MB

## 給一般使用者（不需要 Python）

1. 到 [Releases](../../releases) 下載 `KeyOverlay.exe`
2. 雙擊執行。第一次開啟若出現 SmartScreen「Windows 已保護您的電腦」→ 點「其他資訊」→「仍要執行」（exe 沒有程式碼簽章）
3. 在設定視窗選顏色 →「開始執行」（按「取消」則不會啟動任何東西）
4. 結束程式（擇一）：
   - 按 **`Ctrl + Alt + Shift + Q`**
   - 在螢幕右下角通知區域的黃色 **K** 圖示按右鍵 →「結束 Key Overlay」（Windows 11 若沒看到圖示，點工作列右側的 `^` 展開）
   - 程式已在執行時再開一次，會提示關閉方式

開機自動啟動：`Win + R` → 輸入 `shell:startup` → 放一個 `KeyOverlay.exe` 的捷徑，並在捷徑「目標」後面空一格加上 `--no-dialog`，開機時就不會跳設定視窗、直接沿用上次的選擇。

## 參數

| 參數 | 預設 | 說明 |
| :-- | :-- | :-- |
| `--font-size N` | 20 | 字級（pt） |
| `--hold SEC` | 1.5 | 放開後停留秒數 |
| `--margin PX` | 24 | 與螢幕邊緣距離 |
| `--opacity 0.1~1.0` | 0.92 | 不透明度 |
| `--theme yellow\|blue\|white` | 上次的選擇，否則 `yellow` | 顯示顏色 |
| `--combos-only` | 上次的選擇，否則關 | 只在按住 Ctrl/Alt/Win 時顯示，一般打字（含密碼）不會出現在畫面上 |
| `--no-dialog` | 關 | 不跳設定視窗，直接啟動（給開機自動啟動用） |
| `--preview "Ctrl+Shift+Z"` | — | 只畫出指定組合、不掛鍵盤 hook（開發時看配色用，從右下角圖示結束） |

exe 也吃同樣的參數，可在捷徑的「目標」後面加，例如 `KeyOverlay.exe --combos-only --font-size 16`。

## 開發

```powershell
python -m key_overlay              # 從原始碼執行（有 console）
pythonw KeyOverlay.pyw             # 不開 console
python -m unittest discover -s tests -v
./build.ps1                        # 產出 dist/KeyOverlay.exe
```

結構：

```
key_overlay/
  keys.py      VK 代碼 → 顯示名稱、按住狀態（純邏輯，有單元測試）
  hook.py      WH_KEYBOARD_LL hook thread，事件丟進 queue
  render.py    配色主題與鍵帽繪製（overlay 與設定視窗共用）
  launcher.py  啟動設定視窗、settings.json 讀寫
  tray.py      右下角通知區域圖示與右鍵選單（Shell_NotifyIconW，獨立 thread）
  app.py       tkinter overlay、事件轉送（relay thread → <<Input>>）、CLI 參數、啟動流程
  assets/icon.ico  由 tools/make_icon.py 產生（純 stdlib 寫 ICO）
```

## 發佈新版

GitHub Actions（`.github/workflows/build.yml`）在每次 push 跑測試並打包 exe（Actions artifact）；推 `v*` tag 時自動建立 Release 並附上 exe：

```powershell
# 先改 key_overlay/__init__.py 的 __version__
git tag v0.1.0
git push origin v0.1.0
```

## 已知限制

- **以系統管理員身分執行的視窗**（工作管理員、部分安裝程式）裡的按鍵抓不到，這是 Windows UIPI 的限制；需要時改用「以系統管理員身分執行」開 KeyOverlay
- 鎖定畫面、UAC 提示等安全桌面上的按鍵抓不到
- 符號鍵名稱以美式鍵盤配置顯示
- 只顯示在主螢幕
- 全域鍵盤 hook 行為類似鍵盤側錄，部分防毒／企業 EDR 可能誤判或封鎖未簽章 exe
