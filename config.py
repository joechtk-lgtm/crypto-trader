CRYPTO_CAPITAL_USD = 1000
GRID_CAPITAL_USD = 500       # 10 levels x $50 each
DCA_RESERVE_USD = 450        # dry powder for DCA triggers
BUFFER_USD = 50              # never touched

DCA_AMOUNT_FULL = 50         # F&G < 20, both funding negative, ETF positive
DCA_AMOUNT_HALF = 25         # F&G < 20, both funding negative, ETF neutral
DCA_AMOUNT_ENHANCED = 75     # F&G < 10, all conditions met (rare)
DCA_ALLOCATION = {"BTC": 0.70, "ETH": 0.30}   # SOL removed, it's in grid only

FEAR_GREED_THRESHOLD = 20
GRID_PAIR = "SOL/USDT"
GRID_LOWER = 70.0
GRID_UPPER = 100.0
GRID_LEVELS = 10
MIN_DAILY_VOLUME_USD = 50_000_000
TIER1 = ["ETH/USDT", "SOL/USDT"]
TIER2 = ["BNB/USDT", "ADA/USDT"]
TIER3 = ["AVAX/USDT", "LINK/USDT", "DOT/USDT"]
