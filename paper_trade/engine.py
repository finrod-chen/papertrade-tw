"""
紙盤交易引擎
手動模式：命令列互動下單、紀錄損益
"""
import uuid
from datetime import datetime
from rich.console import Console
from rich.table import Table
from .position import PositionManager
from .journal import TradeRecord, append_trade, load_journal
from config import (
    COMMISSION_RATE, TAX_RATE, SLIPPAGE,
    INITIAL_CAPITAL, MAX_DAILY_LOSS,
)

console = Console()


def _calc_commission(price: float, size: int, is_sell: bool) -> float:
    comm = price * size * COMMISSION_RATE
    if is_sell:
        comm += price * size * TAX_RATE
    return round(comm, 2)


class PaperEngine:
    def __init__(self, capital: float = INITIAL_CAPITAL):
        self.capital = capital
        self.start_capital = capital
        self.daily_start_capital = capital
        self.pm = PositionManager()
        self._trade_counter = 0

    # ── 下單 ──────────────────────────────────────────────────────────

    def buy(self, stock_id: str, price: float, size: int, note: str = "") -> bool:
        """買進（多單進場）"""
        if price <= 0 or size <= 0:
            console.print(f"[red]參數錯誤：價格與股數必須為正數（price={price}, size={size}）[/red]")
            return False
        if not self._check_daily_loss():
            return False

        # 實際成交價含滑價，後續損益與停損都以此為基準
        actual_price = price * (1 + SLIPPAGE)
        cost = actual_price * size
        commission = _calc_commission(actual_price, size, is_sell=False)
        total_cost = cost + commission

        if total_cost > self.capital:
            console.print(f"[red]資金不足！需要 {total_cost:,.0f}，現有 {self.capital:,.0f}[/red]")
            return False

        self.capital -= total_cost
        self.pm.open(stock_id, actual_price, size, entry_commission=commission)

        console.print(
            f"[green]✓ 買進 {stock_id}  {size}股 @ {actual_price:.2f}(含滑價)  "
            f"手續費:{commission:.0f}  剩餘資金:{self.capital:,.0f}[/green]"
        )
        return True

    def sell(self, stock_id: str, price: float, exit_reason: str = "SIGNAL", note: str = "") -> bool:
        """賣出平倉（多單出場）"""
        if price <= 0:
            console.print(f"[red]參數錯誤：價格必須為正數（price={price}）[/red]")
            return False
        pos = self.pm.get(stock_id)
        if not pos:
            console.print(f"[red]無 {stock_id} 部位[/red]")
            return False

        actual_price = price * (1 - SLIPPAGE)
        sell_commission = _calc_commission(actual_price, pos.size, is_sell=True)
        proceeds = actual_price * pos.size - sell_commission
        gross_pnl = (actual_price - pos.entry_price) * pos.size
        # 淨損益 = 毛損益 - 賣出成本 - 買進手續費（買進時已自資金扣除）
        total_commission = sell_commission + pos.entry_commission
        net_pnl = gross_pnl - total_commission

        self.capital += proceeds
        self.pm.close(stock_id)
        self._trade_counter += 1  # 以「平倉」為一筆完整交易編號，確保 ID 唯一

        record = TradeRecord(
            trade_id=f"T{self._trade_counter:05d}",
            stock_id=stock_id,
            side="BUY",
            entry_time=pos.entry_time.strftime("%Y-%m-%d %H:%M:%S"),
            entry_price=pos.entry_price,
            exit_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            exit_price=price,
            size=pos.size,
            gross_pnl=round(gross_pnl, 0),
            commission=round(total_commission, 0),
            net_pnl=round(net_pnl, 0),
            exit_reason=exit_reason,
            note=note,
        )
        append_trade(record)

        color = "green" if net_pnl >= 0 else "red"
        console.print(
            f"[{color}]✓ 賣出 {stock_id}  {pos.size}股 @ {price:.2f}  "
            f"淨損益:{net_pnl:+,.0f}  ({exit_reason})[/{color}]"
        )
        return True

    # ── 風控 ─────────────────────────────────────────────────────────

    def _check_daily_loss(self) -> bool:
        # 以「現金 + 持倉成本」估算權益：買進本身不是虧損，
        # 只有已實現虧損才會讓這個值下降（未實現損益需即時報價，不計入）
        position_cost = sum(
            p.entry_price * abs(p.size) + p.entry_commission
            for p in self.pm.all_positions()
        )
        equity_basis = self.capital + position_cost
        daily_loss = (equity_basis - self.daily_start_capital) / self.daily_start_capital
        if daily_loss <= -MAX_DAILY_LOSS:
            console.print(
                f"[bold red]⚠ 單日虧損達 {daily_loss*100:.1f}%，今日停止交易！[/bold red]"
            )
            return False
        return True

    def check_stop_losses(self, prices: dict[str, float]):
        """傳入 {stock_id: current_price}，自動觸發停損"""
        for stock_id, price in prices.items():
            if self.pm.should_stop_loss(stock_id, price):
                console.print(f"[yellow]⚡ 停損觸發：{stock_id} @ {price:.2f}[/yellow]")
                self.sell(stock_id, price, exit_reason="STOP_LOSS")

    def close_all_eod(self, prices: dict[str, float]):
        """收盤前強制平所有部位"""
        for pos in self.pm.all_positions():
            price = prices.get(pos.stock_id)
            if price:
                self.sell(pos.stock_id, price, exit_reason="EOD")

    # ── 報表 ─────────────────────────────────────────────────────────

    def show_positions(self, prices: dict[str, float] = None):
        table = Table(title="目前部位", show_header=True)
        table.add_column("股票", style="cyan")
        table.add_column("方向")
        table.add_column("股數", justify="right")
        table.add_column("成本", justify="right")
        table.add_column("現價", justify="right")
        table.add_column("未實現損益", justify="right")

        for pos in self.pm.all_positions():
            current = prices.get(pos.stock_id, pos.entry_price) if prices else pos.entry_price
            pnl = pos.unrealized_pnl(current)
            pnl_pct = pos.unrealized_pnl_pct(current)
            color = "green" if pnl >= 0 else "red"
            table.add_row(
                pos.stock_id,
                "多" if pos.is_long else "空",
                f"{pos.size:,}",
                f"{pos.entry_price:.2f}",
                f"{current:.2f}",
                f"[{color}]{pnl:+,.0f} ({pnl_pct:+.1f}%)[/{color}]",
            )

        console.print(table)
        console.print(f"可用資金：[bold]{self.capital:,.0f}[/bold]")

    def show_summary(self):
        records = load_journal()
        if not records:
            console.print("尚無交易紀錄")
            return

        total_pnl = sum(r.net_pnl for r in records)
        wins = [r for r in records if r.net_pnl > 0]
        win_rate = len(wins) / len(records) * 100 if records else 0

        table = Table(title=f"交易總結（共 {len(records)} 筆）")
        table.add_column("指標")
        table.add_column("數值", justify="right")

        table.add_row("總淨損益", f"{total_pnl:+,.0f}")
        table.add_row("勝率", f"{win_rate:.1f}%")
        table.add_row("獲利筆數", str(len(wins)))
        table.add_row("虧損筆數", str(len(records) - len(wins)))
        if wins:
            table.add_row("平均獲利", f"{sum(r.net_pnl for r in wins)/len(wins):,.0f}")
        losers = [r for r in records if r.net_pnl <= 0]
        if losers:
            table.add_row("平均虧損", f"{sum(r.net_pnl for r in losers)/len(losers):,.0f}")

        console.print(table)
