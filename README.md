# PaperTrade TW — 台股紙盤交易系統

> 策略回測 × 盤前掃描 × 紙盤下單 × 紀律計分 —— 一個「誠實」的交易訓練器。

**定位：紀律訓練器，不是賺錢機器。**
本專案對均線／RSI／布林等技術策略做了完整的樣本外驗證（Walk-Forward + IS/OOS 對照），
結論是純技術面日線策略無穩定打敗大盤的能力。系統因此把重心放在
**可以被你控制的事**：停損紀律、當沖紀律、不凹單、不過度交易、不報復交易。

---

## 功能

| 模組 | 說明 |
|------|------|
| **總覽** | 帳戶權益、持倉、累計損益曲線（互動 sparkline） |
| **盤前掃描** | 追蹤清單逐檔計算均線／RSI／布林三策略共識訊號（RSI 採 Wilder 平滑，與回測引擎同源） |
| **紙盤交易** | 即時報價（yfinance，自動判斷上市/上櫃）、下單含滑價與完整交易成本、出場原因記錄 |
| **紀律計分** | 5 維度紀律評分（停損／當沖／不凹單／不過量／不報復）+「你 vs 買 0050 放著」誠實對照 |
| **策略回測** | Backtrader 引擎，5 個策略（v1 均線交叉 → v3 ATR 追蹤停損＋大盤過濾） |
| **驗證工具** | 網格搜索（含最低交易數過濾）、Walk-Forward（含指標熱身段、可選每視窗訓練期優化）、多股票組合回測 |

## 快速開始

```bash
pip install -r requirements.txt

# .env 設定 FinMind Token（免費申請：https://finmindtrade.com）
# FINMIND_TOKEN=你的token

python run_web.py          # → http://127.0.0.1:5000
```

CLI 工具：

```bash
python main.py backtest --stock 2330 --strategy ma_filtered --start 2022-01-01 --end 2024-01-01
python main.py wf       --stock 2330 --grid '{"fast_period":[5,8],"slow_period":[15,20]}'   # 真 Walk-Forward
python main.py compare  --stock 2330
python main.py scan
python main.py paper
```

Docker 部署（image 由 GitHub Actions 自動建置並推到 Docker Hub）：

```bash
docker pull finrodchen/papertrade-tw:latest
docker run -p 5000:5000 -e FINMIND_TOKEN=你的token \
  -v ./logs:/app/logs -v ./data:/app/data finrodchen/papertrade-tw:latest
```

本機建置：

```bash
docker build -t tw-paper-trade .
docker run -p 5000:5000 -e FINMIND_TOKEN=你的token \
  -v ./logs:/app/logs -v ./data:/app/data tw-paper-trade
```

## 架構

```
data/         FinMind 日線行情、三大法人、yfinance 即時報價
strategy/     Backtrader 策略（v1 均線 → v2 趨勢+量能過濾 → v3 ATR 追蹤停損+大盤過濾）
backtest/     回測執行器、策略比較、網格優化、Walk-Forward、組合回測
paper_trade/  紙盤引擎（完整交易成本模型）、部位管理、交易日誌
dashboard/    紀律計分卡、大盤基準對照、績效報表
webapp/       Flask Web App（深色優先、響應式、無前端框架依賴）
scripts/      每日掃描、批量回測、每股參數優化、樣本外驗證
```

## 回測方法論

交易成本完整建模：手續費 0.1425%（雙邊）、證交稅 0.3%（賣出）、滑價 0.05%。

防過擬合三道關卡：

1. **網格搜索**設有最低交易數門檻，排除「一兩筆賭中」的雜訊參數
2. **Walk-Forward** 測試視窗前接指標熱身段（長週期均線在測試期第一天即就緒），
   可選每視窗於訓練期重新優化參數（真 Walk-Forward）
3. **IS/OOS 對照**：訓練期優化 → 從未見過的測試期驗收 → 與同期 buy-and-hold 0050 比較

## 免責聲明

本專案為模擬交易系統，僅供策略研究與交易紀律訓練，不構成任何投資建議。
