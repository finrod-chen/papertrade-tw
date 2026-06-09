"""
布林通道反彈策略
- 進場：昨收跌破下軌，今收反彈回下軌上方（超賣確認反彈）
- 出場：收盤突破中軌（獲利了結）或觸停損
"""
import backtrader as bt
from .base import BaseStrategy


class BollingerBand(BaseStrategy):
    params = (
        ("period", 20),
        ("devfactor", 2.0),
        ("trade_size", 1000),
    )

    def __init__(self):
        self.boll = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.period,
            devfactor=self.p.devfactor,
        )
        self.entry_price = None
        self.order = None

    def next(self):
        if self.order:
            return

        in_position = self.position.size > 0
        close     = self.data.close[0]
        prev_close = self.data.close[-1]
        mid       = self.boll.lines.mid[0]
        bot       = self.boll.lines.bot[0]
        prev_bot  = self.boll.lines.bot[-1]

        if in_position and self.entry_price:
            # 停損
            if self.stop_loss_check(self.entry_price, close):
                self.log(f"停損 @ {close:.2f}")
                self.order = self.sell(size=self.p.trade_size)
                return
            # 中軌平倉
            if close >= mid:
                self.log(f"中軌平倉 @ {close:.2f}  (mid={mid:.2f})")
                self.order = self.sell(size=self.p.trade_size)
                return

        if not in_position:
            # 昨收跌破下軌，今收反彈回下軌上 → 確認反彈
            if prev_close < prev_bot and close > bot:
                self.log(f"布林反彈買入 @ {close:.2f}  下軌:{bot:.2f}")
                self.order = self.buy(size=self.p.trade_size)
                self.entry_price = close

    def notify_order(self, order):
        super().notify_order(order)
        if order.status == order.Completed:
            self.order = None
