"""所有策略的基礎類別（Backtrader 用）"""
import backtrader as bt
from config import COMMISSION_RATE, TAX_RATE, SLIPPAGE, MAX_LOSS_PER_TRADE


class TwStockCommission(bt.CommInfoBase):
    """台股手續費 + 證交稅"""
    params = (
        ("commission", COMMISSION_RATE),
        ("tax", TAX_RATE),
        ("stocklike", True),
        ("commtype", bt.CommInfoBase.COMM_PERC),
    )

    def _getcommission(self, size, price, pseudoexec):
        # 買進：手續費；賣出：手續費 + 證交稅
        commission = abs(size) * price * self.p.commission
        if size < 0:
            commission += abs(size) * price * self.p.tax
        return commission


class BaseStrategy(bt.Strategy):
    """
    所有策略繼承此類別，內建：
    - 停損邏輯（單筆 -MAX_LOSS_PER_TRADE）
    - 每筆交易 log
    """

    def log(self, msg: str, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f"[{dt}] {msg}")

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            side = "買入" if order.isbuy() else "賣出"
            self.log(
                f"{side} {order.data._name} "
                f"價格:{order.executed.price:.2f} "
                f"數量:{int(order.executed.size)} "
                f"手續費:{order.executed.comm:.0f}"
            )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"訂單失敗: {order.Status[order.status]}")

    def notify_trade(self, trade):
        if trade.isclosed:
            self.log(
                f"平倉損益 毛利:{trade.pnl:.0f} 淨利:{trade.pnlcomm:.0f}"
            )

    def stop_loss_check(self, entry_price: float, current_price: float) -> bool:
        """回傳 True 代表觸發停損"""
        loss_pct = (current_price - entry_price) / entry_price
        return loss_pct <= -MAX_LOSS_PER_TRADE
