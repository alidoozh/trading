import requests
import pandas as pd
from datetime import datetime

BINANCE_URL = "https://api.binance.com/api/v3/klines"
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"

def get_spot_price():
    """Spot price با Failover: اول Binance → بعد CoinGecko"""
    try:
        # Binance
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
        r.raise_for_status()
        return float(r.json()["price"])
    except Exception:
        # CoinGecko
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
        r.raise_for_status()
        return float(r.json()["bitcoin"]["usd"])


def get_recent_minutes(symbol="BTCUSDT", interval="15m", limit=240):
    """
    OHLCV دیتا با Failover:
    - اول Binance
    - بعد CoinGecko (فقط close و volume → high/low رو با close پر می‌کنیم)
    """
    try:
        # Binance
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(BINANCE_URL, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data, columns=[
            "timestamp","open","high","low","close","volume",
            "_1","_2","_3","_4","_5","_6"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df[["timestamp","open","high","low","close","volume"]].astype(float)
        return df

    except Exception:
        # CoinGecko (returns 5-min candles, so may differ a bit)
        r = requests.get(COINGECKO_URL, params={"vs_currency": "usd", "days": "7"}, timeout=5)
        r.raise_for_status()
        data = r.json()

        prices = data["prices"]  # [ [timestamp, price], ... ]
        volumes = data["total_volumes"]

        df = pd.DataFrame(prices, columns=["timestamp","close"])
        df["volume"] = [v[1] for v in volumes]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"]  = df["close"]

        return df.tail(limit)
