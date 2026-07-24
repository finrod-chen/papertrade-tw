"""
均線黃金/死亡交叉策略（日線波段版）
- 進場：5MA 上穿 20MA（多單）
- 出場：5MA 下穿 20MA 或觸停損
註：以日線回測時訂單於次日開盤成交，停損基準採實際成交價
    （由 BaseStrategy.notify_order 回填）
"""
import backtrader as bt
from .base import BaseStrategy


class MovingAvgCross(BaseStrategy):
    params = (
        ("fast_period", 5),
        ("slow_period", 20),
        ("trade_size", 1000),  # 每次買 1 張（1000 股）
    )

    def __init__(self):
        self.fast_ma = bt.indicators.SMA(
            self.data.close, period=self.p.fast_period, plotname="MA5"
        )
        self.slow_ma = bt.indicators.SMA(
            self.data.close, period=self.p.slow_period, plotname="MA20"
        )
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        self.entry_price = None
        self.order = None

    def next(self):
        if self.order:
            return

        in_position = self.position.size > 0

        if in_position and self.entry_price:
            # 停損
            if self.stop_loss_check(self.entry_price, self.data.close[0]):
                self.log(f"觸發停損 進場:{self.entry_price:.2f} 現價:{self.data.close[0]:.2f}")
                self.order = self.sell(size=self.p.trade_size)
                return
            # 死亡交叉出場
            if self.crossover < 0:
                self.log(f"死亡交叉 賣出 @ {self.data.close[0]:.2f}")
                self.order = self.sell(size=self.p.trade_size)
                return

        # 進場：黃金交叉
        if not in_position and self.crossover > 0:
            self.log(f"黃金交叉 買入 @ {self.data.close[0]:.2f}")
            self.order = self.buy(size=self.p.trade_size)
            self.entry_price = self.data.close[0]  # 暫記訊號價，成交後回填實際價


class RSIStrategy(BaseStrategy):
    """
    RSI 超賣反彈策略
    - 進場：RSI < 30（超賣）且收盤上穿昨收
    - 出場：RSI > 70 或停損
    """
    params = (
        ("rsi_period", 14),
        ("oversold", 30),
        ("overbought", 70),
        ("trade_size", 1000),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)
        self.entry_price = None
        self.order = None

    def next(self):
        if self.order:
            return

        in_position = self.position.size > 0

        if in_position and self.entry_price:
            if self.stop_loss_check(self.entry_price, self.data.close[0]):
                self.log(f"停損 RSI:{self.rsi[0]:.1f}")
                self.order = self.sell(size=self.p.trade_size)
                return
            if self.rsi[0] > self.p.overbought:
                self.log(f"RSI 超買平倉 RSI:{self.rsi[0]:.1f}")
                self.order = self.sell(size=self.p.trade_size)
                return

        if not in_position and self.rsi[0] < self.p.oversold:
            self.log(f"RSI 超賣買入 RSI:{self.rsi[0]:.1f} @ {self.data.close[0]:.2f}")
            self.order = self.buy(size=self.p.trade_size)
            self.entry_price = self.data.close[0]
