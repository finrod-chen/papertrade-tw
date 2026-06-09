from dotenv import load_dotenv
import os

load_dotenv()

# FinMind API
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")

# 交易成本
COMMISSION_RATE = 0.001425   # 手續費 0.1425%（單邊）
TAX_RATE = 0.003             # 證交稅 0.3%（賣出才收）
SLIPPAGE = 0.0005            # 滑價 0.05%

# 紙盤風控
MAX_LOSS_PER_TRADE = 0.02    # 單筆最大虧損 2%
MAX_DAILY_LOSS = 0.05        # 單日最大虧損 5%
INITIAL_CAPITAL = 1_000_000  # 模擬初始資金 100 萬

# 資料路徑
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
