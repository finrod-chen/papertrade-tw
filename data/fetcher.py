"""FinMind REST API 資料抓取模組（直接呼叫 API，不依賴 finmind 套件）"""
import os
import requests
import pandas as pd
from config import FINMIND_TOKEN, DATA_DIR

_BASE = "https://api.finmindtrade.com/api/v4/data"


def _get(dataset: str, stock_id: str, start: str, end: str) -> dict:
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": start,
        "end_date": end,
        "token": FINMIND_TOKEN,
    }
    resp = requests.get(_BASE, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_daily_ohlcv(stock_id: str, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
    """
    抓取日線 OHLCV。
    start/end 格式：'2023-01-01'
    """
    cache_path = os.path.join(DATA_DIR, f"{stock_id}_{start}_{end}_daily.csv")
    if use_cache and os.path.exists(cache_path):
        print(f"[cache] 讀取 {cache_path}")
        df = pd.read_csv(cache_path, parse_dates=["date"])
        return df

    print(f"[API] 下載 {stock_id} 日線 {start}~{end} ...")
    data = _get("TaiwanStockPrice", stock_id, start, end)

    if data.get("status") != 200 or not data.get("data"):
        raise ValueError(f"查無資料：{stock_id}（{start}~{end}）status={data.get('status')} msg={data.get('msg')}")

    df = pd.DataFrame(data["data"])
    df = df.rename(columns={
        "date": "date",
        "open": "open",
        "max": "high",
        "min": "low",
        "close": "close",
        "Trading_Volume": "volume",
    })
    df["date"] = pd.to_datetime(df["date"])
    df = df[["date", "open", "high", "low", "close", "volume"]].sort_values("date").reset_index(drop=True)
    df.to_csv(cache_path, index=False)
    print(f"[cache] 已儲存 {len(df)} 筆 → {cache_path}")
    return df


def fetch_stock_list() -> pd.DataFrame:
    """取得上市股票清單"""
    params = {"dataset": "TaiwanStockInfo", "token": FINMIND_TOKEN}
    resp = requests.get(_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return pd.DataFrame(data.get("data", []))
