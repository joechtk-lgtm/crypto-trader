import ccxt


_exchange = None


def _get_exchange():
    global _exchange
    if _exchange is None:
        _exchange = ccxt.okx({"enableRateLimit": True})
    return _exchange


def get_funding_rate(symbol: str) -> float:
    """Returns funding rate for a symbol. Converts spot symbol to perp format for OKX."""
    try:
        exchange = _get_exchange()
        # OKX perp format: BTC/USDT -> BTC/USDT:USDT
        base = symbol.split("/")[0]
        perp_symbol = f"{base}/USDT:USDT"
        data = exchange.fetch_funding_rate(perp_symbol)
        return float(data["fundingRate"])
    except Exception:
        return None


def get_ohlcv(symbol: str, timeframe: str = "1d", limit: int = 7):
    try:
        exchange = _get_exchange()
        return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception:
        return None


def get_ticker(symbol: str):
    try:
        exchange = _get_exchange()
        ticker = exchange.fetch_ticker(symbol)
        last = float(ticker["last"])
        volume_usd = float(ticker.get("quoteVolume") or 0)
        return {"last": last, "volume_usd": volume_usd}
    except Exception:
        return None
