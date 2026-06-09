"""
投資組合層級回測
- 資金等分給每支股票
- 彙總整體報酬、Sharpe、交易頻率
- 找出「策略在哪些股票有優勢」的統計基礎
"""
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table
from .runner import run_backtest
from config import INITIAL_CAPITAL

console = Console()


def portfolio_backtest(
    strategy_cls,
    stock_dfs: dict,              # {stock_id: df}
    names: dict = None,           # {stock_id: "台積電"}
    total_capital: float = INITIAL_CAPITAL,
    strategy_params: dict = None,          # 共用參數（若無 per_stock_params）
    per_stock_params: dict = None,         # {stock_id: {params}}，優先於 strategy_params
    extra_data: dict = None,               # {"market": df_0050}
) -> dict:
    """
    多股票組合回測。
    等分資金，各股獨立運作，最後彙總。
    回傳完整 summary dict。
    """
    n      = len(stock_dfs)
    per_cap = total_capital / n

    console.print(
        f"\n[bold cyan]投資組合回測[/bold cyan]  "
        f"{n} 支  總資金 {total_capital:,.0f}  每股 {per_cap:,.0f}\n"
    )

    results = []
    for sid, df in stock_dfs.items():
        params = dict((per_stock_params or {}).get(sid) or strategy_params or {})

        # ── 自動計算合理交易量 ──────────────────────────────────
        # 用資料中位數價格估算，確保 1 筆交易不超過分配資金的 95%
        median_price = float(df["close"].median())
        max_shares   = int(per_cap * 0.90 / median_price)
        # 台股標準張：1000股；ETF也是1000股（或100股，保守取1000）
        auto_size = max(1, (max_shares // 100) * 100)   # 取整至百股
        params.setdefault("trade_size", auto_size)
        # ──────────────────────────────────────────────────────

        try:
            m = run_backtest(
                strategy_cls, df.copy(),
                stock_id=sid, cash=per_cap,
                plot=False,
                strategy_params=params,
                extra_data=extra_data,
            )
            m["name"]       = (names or {}).get(sid, sid)
            m["capital"]    = per_cap
            m["trade_size"] = params["trade_size"]
            m["med_price"]  = round(median_price, 1)
            results.append(m)
        except Exception as e:
            console.print(f"[dim red]  {sid} 失敗: {e}[/dim red]")

    if not results:
        console.print("[red]無有效結果[/red]")
        return {}

    return _aggregate(results, total_capital)


def _aggregate(results: list, total_capital: float) -> dict:
    df = pd.DataFrame(results)

    total_final  = df["final_value"].sum()
    total_ret    = (total_final - total_capital) / total_capital * 100
    pos_cnt      = int((df["total_return_pct"] > 0).sum())
    total_trades = int(df["total_trades"].sum())
    trades_py    = total_trades / 4   # 假設 4 年資料

    valid_wr = df[df["total_trades"] > 0]["win_rate_pct"]
    avg_wr   = float(valid_wr.mean()) if not valid_wr.empty else 0.0

    # 加權夏普（按交易次數加權）
    sdf = df[df["sharpe_ratio"].notna() & (df["total_trades"] > 0)].copy()
    if not sdf.empty:
        avg_sharpe = float(
            (sdf["sharpe_ratio"] * sdf["total_trades"]).sum() / sdf["total_trades"].sum()
        )
    else:
        avg_sharpe = None

    _print_detail_table(df)

    color = "green" if total_ret >= 0 else "red"
    sharpe_str = f"{avg_sharpe:.3f}" if avg_sharpe else "N/A"
    console.print(f"""
[bold]═══ 投資組合彙總 ═══[/bold]
  初始資金   {total_capital:>14,.0f}
  最終資金   {total_final:>14,.0f}
  [{color}]組合報酬   {total_ret:>+13.2f}%[/{color}]
  加權夏普   {sharpe_str}
  正報酬     [cyan]{pos_cnt}/{len(results)}[/cyan] ({pos_cnt/len(results)*100:.0f}%)
  總交易數   [cyan]{total_trades:>4}[/cyan] 筆  (≈ {trades_py:.0f} 筆/年)
  平均勝率   {avg_wr:.1f}%

  [dim]← 交易數 ≥ 30/年 才具統計顯著性[/dim]
""")

    return {
        "total_capital":    total_capital,
        "total_final":      total_final,
        "total_return_pct": round(total_ret, 2),
        "avg_sharpe":       round(avg_sharpe, 3) if avg_sharpe else None,
        "pos_stocks":       pos_cnt,
        "total_stocks":     len(results),
        "total_trades":     total_trades,
        "trades_per_year":  round(trades_py, 1),
        "avg_win_rate":     round(avg_wr, 1),
        "details":          results,
    }


def _print_detail_table(df: pd.DataFrame):
    table = Table(title="個股績效明細", header_style="bold cyan", show_lines=True)
    table.add_column("代號",     style="cyan", width=6)
    table.add_column("名稱",               width=8)
    table.add_column("報酬率%",  justify="right", width=9)
    table.add_column("夏普",     justify="right", width=8)
    table.add_column("回撤%",    justify="right", width=7)
    table.add_column("勝率%",    justify="right", width=7)
    table.add_column("獲利因子", justify="right", width=9)
    table.add_column("交易數",   justify="right", width=7)
    table.add_column("最終資金", justify="right", width=11)

    for _, r in df.sort_values("total_return_pct", ascending=False).iterrows():
        col    = "green" if r["total_return_pct"] > 0 else "red"
        sharpe = f"{r['sharpe_ratio']:.3f}" if r.get("sharpe_ratio") else "N/A"
        table.add_row(
            r["stock_id"], r.get("name", ""),
            f"[{col}]{r['total_return_pct']:+.2f}[/{col}]",
            sharpe,
            f"{r['max_drawdown_pct']:.2f}",
            f"{r['win_rate_pct']:.1f}",
            f"{r['profit_factor']:.2f}",
            str(int(r["total_trades"])),
            f"{r['final_value']:,.0f}",
        )
    console.print(table)


def load_stock_dfs(watchlist: list, start: str, end: str) -> tuple[dict, dict]:
    """批次載入所有股票資料，回傳 (stock_dfs, names)"""
    from data.fetcher import fetch_daily_ohlcv
    stock_dfs, names = {}, {}
    for s in watchlist:
        sid = s["id"]
        try:
            df = fetch_daily_ohlcv(sid, start, end, use_cache=True)
            if len(df) >= 80:
                stock_dfs[sid] = df
                names[sid] = s["name"]
            else:
                console.print(f"[dim]{sid} 資料不足，跳過[/dim]")
        except Exception as e:
            console.print(f"[dim red]{sid} 載入失敗: {e}[/dim red]")
    return stock_dfs, names
