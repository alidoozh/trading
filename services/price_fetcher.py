import requests
import pandas as pd
from datetime import datetime

# === قیمت لحظه‌ای از نوبیتکس ===
def get_spot_price(symbol: str = "BTCUSDT") -> float:
    """
    قیمت لحظه‌ای اسپات رو از Nobitex میاره.
    """
    url = f"https://api.nobitex.ir/v2/orderbook/{symbol.lower()}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return float(data["lastTradePrice"])
    except Exception as e:
        raise RuntimeError(f"Failed to fetch spot price from Nobitex: {e}")


# === دریافت کندل‌ها (OHLCV) از نوبیتکس ===
def get_recent_minutes(symbol: str = "BTCUSDT", limit: int = 240) -> pd.DataFrame:
    """
    OHLCV دیتای دقیقه‌ای از Nobitex
    """
    url = "https://api.nobitex.ir/market/candles"
    payload = {
        "symbol": symbol.lower(),
        "resolution": "1",   # 1 دقیقه‌ای
        "limit": str(limit)
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
        data = r.json()

        if "candles" not in data or not data["candles"]:
            raise ValueError("No candle data in response")

        # ساخت DataFrame
        df = pd.DataFrame(data["candles"], columns=["time","open","high","low","close","volume"])
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.astype({
            "open": float, "high": float, "low": float,
            "close": float, "volume": float
        })
        df.set_index("time", inplace=True)
        return df

    except Exception as e:
        raise RuntimeError(f"Failed to fetch OHLCV from Nobitex: {e}")
