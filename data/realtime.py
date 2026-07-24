"""
即時/盤中報價 — Yahoo Finance (yfinance)
台股代碼規則：上市 .TW，上櫃 .TWO
查價時先試 .TW，失敗自動改試 .TWO，成功的後綴會快取供之後使用。
使用方法：
    from data.realtime import get_price, get_prices
    price = get_price("2330")           # → 800.0
    prices = get_prices(["2330","2317"])# → {"2330": 800.0, "2317": 105.5}
"""
import yfinance as yf
import pandas as pd
from typing import Optional

_SUFFIXES = (".TW", ".TWO")
_SUFFIX_CACHE: dict[str, str] = {}   # {stock_id: 已確認可用的後綴}


def _fetch_price(ticker: str) -> Optional[float]:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = getattr(info, "last_price", None)
        if price is None or price == 0:
            # fallback：用最近一筆 1 分 K
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        return float(price) if price else None
    except Exception:
        return None


def _candidate_suffixes(stock_id: str) -> tuple:
    cached = _SUFFIX_CACHE.get(stock_id)
    if cached:
        return (cached,) + tuple(s for s in _SUFFIXES if s != cached)
    return _SUFFIXES


def get_price(stock_id: str) -> Optional[float]:
    """取得最新成交價（收盤或盤中即時），自動嘗試上市/上櫃後綴"""
    for suffix in _candidate_suffixes(stock_id):
        price = _fetch_price(f"{stock_id}{suffix}")
        if price:
            _SUFFIX_CACHE[stock_id] = suffix
            return price
    return None


def get_prices(stock_ids: list) -> dict:
    """批次取得多支股票最新價，回傳 {stock_id: price}"""
    result = {}
    for sid in stock_ids:
        price = get_price(sid)
        if price:
            result[sid] = price
        else:
            print(f"[realtime] {sid} 取價失敗（非交易時間或代碼錯誤）")
    return result


def get_intraday_ohlcv(stock_id: str, interval: str = "5m") -> Optional[pd.DataFrame]:
    """
    取得盤中分鐘 K。
    interval 選項：1m, 2m, 5m, 15m, 30m, 60m
    """
    for suffix in _candidate_suffixes(stock_id):
        try:
            t = yf.Ticker(f"{stock_id}{suffix}")
            df = t.history(period="1d", interval=interval)
            if df.empty:
                continue
            _SUFFIX_CACHE[stock_id] = suffix
            df.index = pd.to_datetime(df.index)
            df.columns = [c.lower() for c in df.columns]
            df = df[["open", "high", "low", "close", "volume"]].copy()
            df.index.name = "datetime"
            return df
        except Exception as e:
            print(f"[realtime] {stock_id}{suffix} 分 K 失敗: {e}")
    return None


def show_live_portfolio(positions: list, engine=None) -> dict:
    """
    給 paper_trade engine 用：
    傳入 [{"stock_id": "2330", ...}, ...] 回傳即時損益
    """
    stock_ids = [p["stock_id"] if isinstance(p, dict) else p.stock_id for p in positions]
    prices = get_prices(stock_ids)

    if engine:
        engine.show_positions(prices)

    return prices
