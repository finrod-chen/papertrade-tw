"""
台股當沖紙盤交易系統 — 主程式
用法：
  py main.py backtest  --stock 2330 --start 2022-01-01 --end 2024-01-01
  py main.py compare   --stock 2330 --start 2022-01-01 --end 2024-01-01
  py main.py wf        --stock 2330 --start 2020-01-01 --end 2024-01-01
  py main.py scan
  py main.py paper
  py main.py report
"""
import argparse
import sys


# ── A. 回測 ──────────────────────────────────────────────────────

def cmd_backtest(args):
    from dotenv import load_dotenv; load_dotenv()
    from data.fetcher import fetch_daily_ohlcv
    from backtest.runner import run_backtest
    from strategy import STRATEGIES

    cls = STRATEGIES.get(args.strategy)
    if not cls:
        print(f"未知策略 '{args.strategy}'，可用：{list(STRATEGIES.keys())}")
        sys.exit(1)

    df = fetch_daily_ohlcv(args.stock, args.start, args.end)
    print(f"載入 {len(df)} 根 K 棒  ({args.start} ~ {args.end})")
    run_backtest(cls, df, stock_id=args.stock, plot=not args.no_plot)


# ── A. 策略比較 ───────────────────────────────────────────────────

def cmd_compare(args):
    from dotenv import load_dotenv; load_dotenv()
    from data.fetcher import fetch_daily_ohlcv
    from backtest.compare import compare_strategies
    from strategy import STRATEGIES

    df = fetch_daily_ohlcv(args.stock, args.start, args.end)
    print(f"載入 {len(df)} 根 K 棒，對 {len(STRATEGIES)} 個策略進行比較")
    compare_strategies(STRATEGIES, df, stock_id=args.stock, plot=False)


# ── 網格搜索 ─────────────────────────────────────────────────────

def cmd_optimize(args):
    from dotenv import load_dotenv; load_dotenv()
    from data.fetcher import fetch_daily_ohlcv
    from backtest.optimizer import grid_search
    from strategy import STRATEGIES
    import json

    cls = STRATEGIES.get(args.strategy)
    if not cls:
        print(f"未知策略 '{args.strategy}'，可用：{list(STRATEGIES.keys())}")
        return

    df = fetch_daily_ohlcv(args.stock, args.start, args.end)
    param_grid = json.loads(args.grid)
    grid_search(cls, df, param_grid, stock_id=args.stock, metric=args.metric)


# ── 多股票批量測試 ────────────────────────────────────────────────

def cmd_multi(args):
    from dotenv import load_dotenv; load_dotenv()
    from scripts.multi_stock_backtest import multi_stock_backtest
    multi_stock_backtest(args.strategy, args.start, args.end, args.min_trades)


# ── C. Walk-Forward ──────────────────────────────────────────────

def cmd_wf(args):
    from dotenv import load_dotenv; load_dotenv()
    from data.fetcher import fetch_daily_ohlcv
    from backtest.walk_forward import walk_forward_test
    from strategy import STRATEGIES

    cls = STRATEGIES.get(args.strategy)
    if not cls:
        print(f"未知策略 '{args.strategy}'，可用：{list(STRATEGIES.keys())}")
        sys.exit(1)

    import json
    param_grid = json.loads(args.grid) if args.grid else None

    df = fetch_daily_ohlcv(args.stock, args.start, args.end)
    print(f"載入 {len(df)} 根 K 棒")
    walk_forward_test(
        cls, df,
        stock_id=args.stock,
        train_days=args.train,
        test_days=args.test,
        step_days=args.step,
        param_grid=param_grid,
    )


# ── 投資組合回測 ─────────────────────────────────────────────────

def cmd_portfolio(args):
    from dotenv import load_dotenv; load_dotenv()
    from scripts.portfolio_run import run as portfolio_run
    portfolio_run(
        strategy_name = args.strategy,
        start         = args.start,
        end           = args.end,
        use_optimal   = args.use_optimal,
        use_market    = not args.no_market,
    )


# ── 每股參數優化 ─────────────────────────────────────────────────

def cmd_per_stock_opt(args):
    from dotenv import load_dotenv; load_dotenv()
    from scripts.per_stock_optimize import optimize_all
    optimize_all(args.start, args.end, args.force, args.min_trades)


# ── B. 日報掃描 ───────────────────────────────────────────────────

def cmd_scan(args):
    from dotenv import load_dotenv; load_dotenv()
    from scripts.daily_scan import run_scan
    run_scan(lookback_days=args.lookback)


# ── 紙盤 ──────────────────────────────────────────────────────────

def cmd_paper(args):
    from dotenv import load_dotenv; load_dotenv()
    from paper_trade.engine import PaperEngine
    from rich.console import Console

    console = Console()
    engine  = PaperEngine()

    console.print("[bold cyan]紙盤交易系統啟動[/bold cyan]  [dim]定位：紀律訓練（非打敗大盤）[/dim]")
    console.print("指令：buy / sell / pos / live / stop / eod / summary / score / quit\n")
    console.print("[dim]buy  <股票> <價格> <股數>   → 買進[/dim]")
    console.print("[dim]sell <股票> <價格>          → 賣出[/dim]")
    console.print("[dim]pos                         → 看部位[/dim]")
    console.print("[dim]live <股票1> <股票2>...      → 即時報價更新部位損益[/dim]")
    console.print("[dim]eod  <股票>=<價格> ...       → 收盤強制平倉[/dim]")
    console.print("[dim]stop <股票>=<價格> ...       → 停損掃描[/dim]")
    console.print("[dim]summary                     → 交易統計[/dim]")
    console.print("[dim]score                       → 紀律計分卡 + 大盤對照[/dim]\n")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue

        parts = raw.split()
        cmd   = parts[0].lower()

        if cmd == "quit":
            break

        elif cmd == "buy" and len(parts) >= 4:
            engine.buy(parts[1], float(parts[2]), int(parts[3]))

        elif cmd == "sell" and len(parts) >= 3:
            engine.sell(parts[1], float(parts[2]))

        elif cmd == "pos":
            engine.show_positions()

        elif cmd == "live":
            # live 2330 2317  → 用 yfinance 取即時價更新損益
            try:
                from data.realtime import get_prices
                ids    = parts[1:] if len(parts) > 1 else [p.stock_id for p in engine.pm.all_positions()]
                prices = get_prices(ids)
                engine.show_positions(prices)
            except ImportError:
                console.print("[red]需安裝 yfinance：py -m pip install yfinance[/red]")

        elif cmd == "eod":
            prices = {}
            for p in parts[1:]:
                sid, price = p.split("=")
                prices[sid] = float(price)
            engine.close_all_eod(prices)

        elif cmd == "stop":
            prices = {}
            for p in parts[1:]:
                sid, price = p.split("=")
                prices[sid] = float(price)
            engine.check_stop_losses(prices)

        elif cmd == "summary":
            engine.show_summary()

        elif cmd == "score":
            from dashboard.discipline import show_scorecard
            from dashboard.benchmark import benchmark_compare
            show_scorecard()
            print()
            benchmark_compare()

        else:
            console.print("[yellow]未知指令[/yellow]")


# ── 績效報表 ──────────────────────────────────────────────────────

def cmd_report(args):
    from dashboard.report import build_report
    build_report()


# ── 紀律計分卡 ────────────────────────────────────────────────────

def cmd_discipline(args):
    from dashboard.discipline import show_scorecard
    from dashboard.benchmark import benchmark_compare
    show_scorecard()
    print()
    benchmark_compare()


# ── CLI 入口 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="台股當沖紙盤交易系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # backtest
    p = sub.add_parser("backtest", help="單一策略回測")
    p.add_argument("--stock",    default="2330")
    p.add_argument("--start",    default="2022-01-01")
    p.add_argument("--end",      default="2024-01-01")
    p.add_argument("--strategy", default="ma_cross",
                   help="ma_cross | rsi | bollinger")
    p.add_argument("--no-plot",  action="store_true")

    # compare
    p = sub.add_parser("compare", help="所有策略比較")
    p.add_argument("--stock",  default="2330")
    p.add_argument("--start",  default="2022-01-01")
    p.add_argument("--end",    default="2024-01-01")

    # walk-forward
    p = sub.add_parser("wf", help="Walk-Forward 防過擬合測試")
    p.add_argument("--stock",    default="2330")
    p.add_argument("--start",    default="2020-01-01")
    p.add_argument("--end",      default="2024-01-01")
    p.add_argument("--strategy", default="ma_cross")
    p.add_argument("--train",    type=int, default=252, help="訓練天數 (預設252)")
    p.add_argument("--test",     type=int, default=63,  help="OOS測試天數 (預設63)")
    p.add_argument("--step",     type=int, default=63,  help="滾動步長 (預設63)")
    p.add_argument("--grid",     default=None,
                   help='JSON 參數網格；提供後每視窗於訓練期優化（真 Walk-Forward），'
                        '如 \'{"fast_period":[5,8],"slow_period":[15,20]}\'')

    # optimize (網格搜索)
    p = sub.add_parser("optimize", help="參數網格搜索")
    p.add_argument("--stock",    default="2330")
    p.add_argument("--start",    default="2022-01-01")
    p.add_argument("--end",      default="2024-01-01")
    p.add_argument("--strategy", default="ma_filtered")
    p.add_argument("--metric",   default="sharpe_ratio",
                   help="優化目標: sharpe_ratio|total_return_pct|win_rate_pct")
    p.add_argument("--grid",     default='{"fast_period":[3,5,8],"slow_period":[15,20,30]}',
                   help="JSON 格式參數網格")

    # multi (多股票批量測試)
    p = sub.add_parser("multi", help="多股票批量回測")
    p.add_argument("--strategy",    default="ma_filtered")
    p.add_argument("--start",       default="2022-01-01")
    p.add_argument("--end",         default="2024-01-01")
    p.add_argument("--min-trades",  type=int, default=3, dest="min_trades")

    # portfolio
    p = sub.add_parser("portfolio", help="投資組合回測（18支股票）")
    p.add_argument("--strategy",     default="ma_filtered")
    p.add_argument("--start",        default="2020-01-01")
    p.add_argument("--end",          default="2024-01-01")
    p.add_argument("--use-optimal",  action="store_true", default=True, dest="use_optimal")
    p.add_argument("--no-market",    action="store_true")

    # per-stock-opt
    p = sub.add_parser("per-opt", help="每股個別參數優化")
    p.add_argument("--start",       default="2020-01-01")
    p.add_argument("--end",         default="2024-01-01")
    p.add_argument("--force",       action="store_true")
    p.add_argument("--min-trades",  type=int, default=3, dest="min_trades")

    # scan
    p = sub.add_parser("scan", help="盤前訊號掃描")
    p.add_argument("--lookback", type=int, default=60, help="回溯天數 (預設60)")

    # paper
    sub.add_parser("paper", help="紙盤交易（互動模式）")

    # report
    sub.add_parser("report", help="績效報表")

    # discipline (紀律計分卡 + 大盤對照)
    sub.add_parser("discipline", help="紀律計分卡 + 大盤基準對照")

    args = parser.parse_args()

    dispatch = {
        "backtest":  cmd_backtest,
        "portfolio": cmd_portfolio,
        "per-opt":   cmd_per_stock_opt,
        "discipline":cmd_discipline,
        "compare":  cmd_compare,
        "wf":       cmd_wf,
        "optimize": cmd_optimize,
        "multi":    cmd_multi,
        "scan":     cmd_scan,
        "paper":    cmd_paper,
        "report":   cmd_report,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
