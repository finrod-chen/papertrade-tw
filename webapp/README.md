# 台股紙盤交易系統 — Web App

簡潔易用的網頁版，整合盤前掃描、紙盤交易、紀律計分、策略回測。
**定位：紀律訓練器**（經樣本外驗證，純技術面日線當沖無打敗大盤能力，故重點在練紀律）。

---

## 一、本機啟動（開發）

```bash
# 1. 安裝依賴（首次）
py -m pip install -r requirements.txt

# 2. 設定 FinMind Token（.env 檔）
#    FINMIND_TOKEN=你的token

# 3. 啟動
py run_web.py

# 4. 瀏覽器開啟
#    http://127.0.0.1:5000
```

換埠號：`set PORT=8080 && py run_web.py`（Windows）

---

## 二、功能頁籤

| 頁籤 | 功能 |
|------|------|
| **總覽** | 帳戶權益、現金、持倉市值、今日已實現損益 |
| **盤前掃描** | 18 支追蹤股的均線/RSI/布林三策略共識訊號 |
| **紙盤交易** | 即時報價下單、持倉管理、一鍵賣出、交易日誌 |
| **紀律計分** | 5 維度紀律評分 + 「你 vs 買大盤放著」誠實對照 |
| **策略回測** | 任選股票/策略/期間，輸出報酬、夏普、勝率等 |

---

## 三、正式部署（Linux 伺服器）

使用 gunicorn（生產級 WSGI server）：

```bash
pip install -r requirements.txt
gunicorn -w 2 -b 0.0.0.0:5000 "webapp.app:app"
```

### Docker 部署

專案根目錄已附 `Dockerfile`：

```bash
docker build -t tw-paper-trade .
docker run -p 5000:5000 -e FINMIND_TOKEN=你的token tw-paper-trade
```

---

## 四、資料持久化

| 檔案 | 內容 |
|------|------|
| `logs/paper_state.json` | 紙盤帳戶資金與持倉（跨重啟保留） |
| `logs/trade_journal.csv` | 交易日誌（紀律計分來源） |
| `data/raw/*.csv` | 行情快取 |

> 部署時請掛載 `logs/` 與 `data/` 為持久卷（volume），避免重啟遺失。

---

## 五、注意事項

- 即時報價來自 yfinance，**非交易時間**可能取不到價，可手動輸入。
- 掃描需逐檔抓資料，約 20–40 秒，屬正常。
- 本系統純供策略驗證與紀律訓練，**非投資建議**。
