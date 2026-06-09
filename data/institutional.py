"""
三大法人資料抓取與分析
資料來源：FinMind TaiwanStockInstitutionalInvestorsBuySell

欄位：
  Foreign_Investor_buy  / sell  → 外資買賣超（最重要）
  Investment_Trust_buy  / sell  → 投信
  Dealer_buy            / sell  → 自營商
"""
import os
import requests
import pandas as pd
from config import FINMIND_TOKEN, DATA_DIR

_BASE = "https://api.finmindtrade.com/api/v4/data"


def fetch_institutional(stock_id: str, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
    """
    抓取三大法人買賣超資料。
    回傳欄位：date, foreign_net, trust_net, dealer_net, total_net
    """
    cache_path = os.path.join(DATA_DIR, f"{stock_id}_{start}_{end}_inst.csv")
    if use_cache and os.path.exists(cache_path):
        return pd.read_csv(cache_path, parse_dates=["date"])

    print(f"[API] 下載 {stock_id} 三大法人 {start}~{end} ...")
    params = {
        "dataset":    "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id":    stock_id,
        "start_date": start,
        "end_date":   end,
        "token":      FINMIND_TOKEN,
    }
    resp = requests.get(_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != 200 or not data.get("data"):
        raise ValueError(f"三大法人查無資料：{stock_id}")

    raw = pd.DataFrame(data["data"])
    raw["date"] = pd.to_datetime(raw["date"])
    raw["net"]  = raw["buy"].fillna(0) - raw["sell"].fillna(0)

    # pivot：每個法人名稱變一欄
    pivot = raw.pivot_table(index="date", columns="name", values="net",
                            aggfunc="sum").fillna(0)
    pivot.columns = [c.lower().replace(" ", "_") for c in pivot.columns]

    # 取外資、投信、自營商淨買賣（欄位名稱依 FinMind 實際回傳）
    def _get(df, *keys):
        for k in keys:
            if k in df.columns:
                return df[k]
        return pd.Series(0, index=df.index)

    df = pd.DataFrame(index=pivot.index)
    df["foreign_net"] = _get(pivot, "foreign_investor", "foreign_investor_buy")
    df["trust_net"]   = _get(pivot, "investment_trust")
    df["dealer_net"]  = _get(pivot, "dealer_self", "dealer")
    df["total_net"]   = df["foreign_net"] + df["trust_net"] + df["dealer_net"]
    df = df.reset_index().rename(columns={"index": "date"})

    out = df.sort_values("date").reset_index(drop=True)
    out.to_csv(cache_path, index=False)
    return out


def add_institutional_signal(ohlcv_df: pd.DataFrame, inst_df: pd.DataFrame,
                              consecutive_days: int = 3) -> pd.DataFrame:
    """
    把三大法人訊號合併進 OHLCV DataFrame。

    新增欄位：
      foreign_net         → 當日外資淨買賣（股數）
      foreign_consec_buy  → 外資連續買超天數（正值）
      inst_buy_signal     → True = 外資連買 N 天以上
    """
    df = ohlcv_df.copy()
    inst = inst_df[["date", "foreign_net", "total_net"]].copy()

    df = df.merge(inst, on="date", how="left")
    df["foreign_net"]  = df["foreign_net"].fillna(0)
    df["total_net"]    = df["total_net"].fillna(0)

    # 計算連續買超天數
    consec = []
    count = 0
    for net in df["foreign_net"]:
        if net > 0:
            count += 1
        else:
            count = 0
        consec.append(count)
    df["foreign_consec_buy"] = consec
    df["inst_buy_signal"]    = df["foreign_consec_buy"] >= consecutive_days

    return df


def institutional_summary(inst_df: pd.DataFrame, last_n: int = 10) -> dict:
    """最近 N 天三大法人統計"""
    recent = inst_df.tail(last_n)
    return {
        "foreign_total":  int(recent["foreign_net"].sum()),
        "trust_total":    int(recent["trust_net"].sum()),
        "dealer_total":   int(recent["dealer_net"].sum()),
        "buy_days":       int((recent["foreign_net"] > 0).sum()),
        "sell_days":      int((recent["foreign_net"] < 0).sum()),
        "consec_buy":     int((recent["foreign_net"] > 0).iloc[::-1].cumprod().sum()),
    }
