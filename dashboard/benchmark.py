"""
大盤基準對照（Benchmark Reality Check）
==========================================
系統轉向後的「誠實之鏡」。

每次看績效，都強制對照「同期間什麼都不做、只買 0050 放著」的報酬。
這是防止自我欺騙的疫苗——OOS 驗證告訴我們，買大盤放著往往完勝主動交易。
"""
import os
from datetime import datetime
from rich.console import Console
from rich.table import Table
from paper_trade.journal import load_journal
from config import INITIAL_CAPITAL

console = Console()


def _parse(ts: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return datetime.now()


def benchmark_compare(benchmark_id: str = "0050"):
    records = load_journal()
    if not records:
        console.print("[yellow]尚無交易紀錄[/yellow]")
        return

    # 紙盤期間
    start_dt = min(_parse(r.entry_time) for r in records)
    end_dt   = max(_parse(r.exit_time)  for r in records)
    start = start_dt.strftime("%Y-%m-%d")
    end   = end_dt.strftime("%Y-%m-%d")

    # 紙盤總損益
    paper_pnl = sum(r.net_pnl for r in records)
    paper_ret = paper_pnl / INITIAL_CAPITAL * 100

    # 基準：同期間 buy-and-hold
    try:
        from data.fetcher import fetch_daily_ohlcv
        bdf = fetch_daily_ohlcv(benchmark_id, start, end, use_cache=True)
        if len(bdf) < 2:
            raise ValueError("基準資料不足")
        bench_ret = (bdf.iloc[-1]["close"] - bdf.iloc[0]["close"]) / bdf.iloc[0]["close"] * 100
        bench_ok = True
    except Exception as e:
        console.print(f"[dim red]基準資料抓取失敗: {e}[/dim red]")
        bench_ret, bench_ok = 0.0, False

    # 對照表
    table = Table(title=f"誠實之鏡：你 vs 買進持有 {benchmark_id}",
                  header_style="bold cyan", show_lines=True)
    table.add_column("項目", width=20)
    table.add_column("報酬率", justify="right", width=12)
    table.add_column("說明", width=28)

    pc = "green" if paper_ret >= 0 else "red"
    table.add_row("你的紙盤交易", f"[{pc}]{paper_ret:+.2f}%[/{pc}]",
                  f"{len(records)} 筆交易換來的")
    if bench_ok:
        bc = "green" if bench_ret >= 0 else "red"
        table.add_row(f"買 {benchmark_id} 放著不動", f"[{bc}]{bench_ret:+.2f}%[/{bc}]",
                      "零交易、零手續費、零壓力")
        diff = paper_ret - bench_ret
        dc = "green" if diff >= 0 else "red"
        table.add_row("你的超額報酬", f"[{dc}]{diff:+.2f}%[/{dc}]",
                      "正值才代表主動交易有意義")

    console.print(table)
    console.print(f"[dim]期間：{start} ~ {end}[/dim]\n")

    if bench_ok:
        if paper_ret > bench_ret:
            console.print("[green]✓ 這段期間你贏過大盤——但別自滿，問自己：是技術還是運氣？[/green]")
        else:
            console.print("[yellow]✗ 跑輸大盤。記住：這不丟臉，多數專業經理人也輸。"
                          "紙盤的價值在練紀律，不在打敗大盤。[/yellow]")
