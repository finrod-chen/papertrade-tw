"""
每日盤前掃描腳本
用法：py scripts/daily_scan.py
功能：
  - 對追蹤清單所有股票計算 MA / RSI / 布林三策略訊號
  - 輸出共識 BUY 候選，儲存 logs/scan_YYYYMMDD.json
"""
import sys
import os
import json
from datetime import datetime, timedelta

# 讓 scripts/ 也能 import 根目錄模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from data.fetcher import fetch_daily_ohlcv
from strategy.signals import consensus_signal
from rich.console import Console
from rich.table import Table

console = Console()

# ── 追蹤清單 ─────────────────────────────────────────────────────
DEFAULT_WATCHLIST = [
    {"id": "2330", "name": "台積電"},
    {"id": "2317", "name": "鴻海"},
    {"id": "2454", "name": "聯發科"},
    {"id": "2382", "name": "廣達"},
    {"id": "2308", "name": "台達電"},
    {"id": "3711", "name": "日月光投控"},
    {"id": "2881", "name": "富邦金"},
    {"id": "2412", "name": "中華電"},
    {"id": "0050", "name": "元大台灣50"},
]

WATCHLIST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "watchlist.json"
)


def load_watchlist() -> list:
    if os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # 第一次執行時存下來
    save_watchlist(DEFAULT_WATCHLIST)
    return DEFAULT_WATCHLIST


def save_watchlist(watchlist: list):
    os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


# ── 訊號顏色 ─────────────────────────────────────────────────────

def _color(signal: str) -> str:
    if signal in ("BUY",):
        return f"[green]{signal}[/green]"
    if signal in ("SELL",):
        return f"[red]{signal}[/red]"
    if signal == "WATCH":
        return f"[yellow]{signal}[/yellow]"
    return f"[dim]{signal or '─'}[/dim]"


# ── 主掃描 ────────────────────────────────────────────────────────

def run_scan(lookback_days: int = 60):
    today    = datetime.today()
    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    watchlist  = load_watchlist()

    console.print(f"\n[bold cyan]盤前掃描  {end_date}[/bold cyan]")
    console.print(f"追蹤 {len(watchlist)} 支，回溯 {lookback_days} 天\n")

    table = Table(show_header=True, header_style="bold", show_lines=False)
    table.add_column("代號",   style="cyan",  width=6)
    table.add_column("名稱",               width=10)
    table.add_column("收盤",  justify="right", width=7)
    table.add_column("RSI",   justify="right", width=6)
    table.add_column("BB%",   justify="right", width=6)
    table.add_column("量比",  justify="right", width=6)
    table.add_column("MA",    justify="center", width=10)
    table.add_column("RSI",   justify="center", width=6)
    table.add_column("布林",  justify="center", width=8)
    table.add_column("共識",  justify="center", width=12)

    buy_candidates = []

    for stock in watchlist:
        try:
            df = fetch_daily_ohlcv(stock["id"], start_date, end_date, use_cache=False)
            if len(df) < 25:
                continue

            sig = consensus_signal(df)

            consensus = sig["consensus"]
            if "BUY" in consensus:
                buy_candidates.append({**stock, **sig})
                c_display = f"[bold green]{consensus}[/bold green]"
            elif "SELL" in consensus:
                c_display = f"[bold red]{consensus}[/bold red]"
            else:
                c_display = f"[dim]{consensus}[/dim]"

            table.add_row(
                stock["id"],
                stock["name"],
                f"{sig['close']:.1f}",
                f"{sig['rsi']:.1f}"   if sig["rsi"]      is not None else "─",
                f"{sig['bb_pct']:.1f}"if sig["bb_pct"]   is not None else "─",
                f"{sig['vol_ratio']:.2f}" if sig["vol_ratio"] is not None else "─",
                _color(sig["ma_signal"]  or "─"),
                _color(sig["rsi_signal"] or "─"),
                _color(sig["bb_signal"]  or "─"),
                c_display,
            )

        except Exception as e:
            console.print(f"[dim red]{stock['id']} 失敗: {e}[/dim red]")

    console.print(table)

    # ── 候選清單 ──
    if buy_candidates:
        console.print("\n[bold green]今日買入候選：[/bold green]")
        for c in buy_candidates:
            console.print(
                f"  [cyan]{c['id']}[/cyan] {c['name']}  "
                f"收盤:{c['close']:.1f}  "
                f"RSI:{c['rsi']}  "
                f"BB%:{c['bb_pct']}  "
                f"共識:[bold]{c['consensus']}[/bold]"
            )
    else:
        console.print("\n[dim]今日無明確買入訊號[/dim]")

    _save_report(buy_candidates, end_date)
    return buy_candidates


def _save_report(candidates: list, date: str):
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"scan_{date.replace('-','')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2, default=str)
    console.print(f"\n[dim]掃描報告：{path}[/dim]")


if __name__ == "__main__":
    run_scan()
