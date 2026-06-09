from .moving_avg import MovingAvgCross, RSIStrategy
from .bollinger import BollingerBand
from .ma_filtered import MAFilteredCross
from .advanced import AdvancedStrategy

# 策略登錄表：新策略只需在這裡加一行，main.py 自動感知
STRATEGIES = {
    "ma_cross":    MovingAvgCross,
    "rsi":         RSIStrategy,
    "bollinger":   BollingerBand,
    "ma_filtered": MAFilteredCross,    # v2：趨勢過濾 + 量能確認
    "advanced":    AdvancedStrategy,   # v3：ATR 追蹤停損 + 大盤過濾
}
