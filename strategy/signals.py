"""
即時訊號產生器 — 純 pandas，不需要 Backtrader
供每日盤前掃描使用
"""
import pandas as pd
import numpy as np
from typing import Optional


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().sort_values("date").reset_index(drop=True)

    # 均線
    df["ma5"]  = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()

    # RSI(14)
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # Bollinger(20, 2)
    df["bb_mid"]   = df["close"].rolling(20).mean()
    std            = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * std
    df["bb_lower"] = df["bb_mid"] - 2 * std
    bb_range = df["bb_upper"] - df["bb_lower"]
    df["bb_pct"]   = (df["close"] - df["bb_lower"]) / bb_range.replace(0, np.nan)

    # 成交量比（今日量 / 5 日均量）
    df["vol_ma5"]   = df["volume"].rolling(5).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma5"].replace(0, np.nan)

    return df


def ma_cross_signal(df: pd.DataFrame) -> Optional[str]:
    """MA5 ✕ MA20 交叉訊號"""
    df = compute_indicators(df)
    if len(df) < 21 or pd.isna(df.iloc[-1]["ma20"]):
        return None
    last, prev = df.iloc[-1], df.iloc[-2]

    if prev["ma5"] <= prev["ma20"] and last["ma5"] > last["ma20"]:
        return "BUY"        # 黃金交叉
    if prev["ma5"] >= prev["ma20"] and last["ma5"] < last["ma20"]:
        return "SELL"       # 死亡交叉
    if last["ma5"] > last["ma20"]:
        return "HOLD_LONG"
    return "HOLD"


def rsi_signal(df: pd.DataFrame) -> Optional[str]:
    """RSI 超買超賣"""
    df = compute_indicators(df)
    if pd.isna(df.iloc[-1]["rsi"]):
        return None
    rsi = df.iloc[-1]["rsi"]

    if rsi < 30:
        return "BUY"
    if rsi > 70:
        return "SELL"
    if rsi < 40:
        return "WATCH"
    return "HOLD"


def bollinger_signal(df: pd.DataFrame) -> Optional[str]:
    """布林通道反彈 / 突破"""
    df = compute_indicators(df)
    if len(df) < 21 or pd.isna(df.iloc[-1]["bb_lower"]):
        return None
    last, prev = df.iloc[-1], df.iloc[-2]

    # 反彈確認：昨破下軌，今收回
    if prev["close"] < prev["bb_lower"] and last["close"] > last["bb_lower"]:
        return "BUY"
    if last["close"] > last["bb_upper"]:
        return "SELL"
    if last["bb_pct"] < 0.1:        # 靠近下軌，關注
        return "WATCH"
    return "HOLD"


def consensus_signal(df: pd.DataFrame) -> dict:
    """
    三策略共識：2/3 以上 BUY → 強/中訊號
    回傳完整數據字典供報表使用
    """
    ma  = ma_cross_signal(df)
    rsi = rsi_signal(df)
    bb  = bollinger_signal(df)

    buy_count  = sum(1 for s in [ma, rsi, bb] if s == "BUY")
    sell_count = sum(1 for s in [ma, rsi, bb] if s == "SELL")

    if buy_count >= 2:
        consensus = f"BUY({'強' if buy_count == 3 else '中'})"
    elif sell_count >= 2:
        consensus = "SELL"
    else:
        consensus = "─"

    df_ind = compute_indicators(df)
    last   = df_ind.iloc[-1]

    def _safe(val):
        return None if (val is None or (isinstance(val, float) and np.isnan(val))) else val

    return {
        "ma_signal":  ma,
        "rsi_signal": rsi,
        "bb_signal":  bb,
        "consensus":  consensus,
        "close":      float(last["close"]),
        "rsi":        round(float(last["rsi"]),    1) if _safe(last["rsi"])      else None,
        "bb_pct":     round(float(last["bb_pct"]) * 100, 1) if _safe(last["bb_pct"]) else None,
        "vol_ratio":  round(float(last["vol_ratio"]), 2) if _safe(last["vol_ratio"]) else None,
        "ma5":        round(float(last["ma5"]),  2) if _safe(last["ma5"])  else None,
        "ma20":       round(float(last["ma20"]), 2) if _safe(last["ma20"]) else None,
    }
