import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone

# ===== تنظیمات با پیش‌فرض‌های امن =====
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "12"))
USER_AGENT = os.getenv("USER_AGENT", "FinalSignalBot/1.0 (+https://example.com)")
OHLCV_CACHE_SECONDS = int(os.getenv("OHLCV_FETCH_INTERVAL", "60"))  # کش کندل‌ها

# کش داخلی
_OHLCV_CACHE = {"df": None, "ts": 0}

def _req(url, params=None, headers=None):
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    r = requests.get(url, params=params, headers=h, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r

# ---------- Spot Providers ----------
def _spot_coincap():
    r = _req("https://api.coincap.io/v2/assets/bitcoin")
    return float(r.json()["data"]["priceUsd"])

def _spot_kraken():
    r = _req("https://api.kraken.com/0/public/Ticker", params={"pair":"XBTUSD"})
    data = r.json()["result"]
    pair_key = next(k for k in data.keys() if k != "last")
    return float(data[pair_key]["c"][0])

def _spot_bitstamp():
    r = _req("https://www.bitstamp.net/api/v2/ticker/btcusd/")
    return float(r.json()["last"])

def _spot_coinbase():
    r = _req("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
    return float(r.json()["price"])

def _spot_bitfinex():
    r = _req("https://api-pub.bitfinex.com/v2/ticker/tBTCUSD")
    # [ BID, BID_SIZE, ASK, ASK_SIZE, DAILY_CHANGE, DAILY_CHANGE_RELATIVE,
    #   LAST_PRICE, VOLUME, HIGH, LOW ]
    arr = r.json()
    return float(arr[6])

def get_spot_price():
    """Spot از چند منبع، به ترتیب آبشاری."""
    errors = []
    for fn in (_spot_coincap, _spot_kraken, _spot_bitstamp, _spot_coinbase, _spot_bitfinex):
        try:
            return fn()
        except Exception as e:
            errors.append(str(e))
    raise RuntimeError("Failed to fetch spot price from all providers: " + " | ".join(errors))

# ---------- OHLCV Providers (1m) ----------
def _ohlc_kraken(limit=240):
    r = _req("https://api.kraken.com/0/public/OHLC", params={"pair":"XBTUSD","interval":1})
    js = r.json()["result"]
    # کلید جفت را (غیر از 'last') بردار
    pair_key = next(k for k in js.keys() if k != "last")
    rows = js[pair_key]
    # ساخت DF با ستون‌های استاندارد
    data = []
    for t, o, h, l, c, vwap, vol, cnt in rows[-limit:]:
        data.append({
            "time": datetime.fromtimestamp(float(t), tz=timezone.utc),
            "open": float(o), "high": float(h), "low": float(l), "close": float(c),
            "volume": float(vol)
        })
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("time").reset_index(drop=True)
    return df

def _ohlc_bitfinex(limit=240):
    # returns list of [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME]
    r = _req("https://api-pub.bitfinex.com/v2/candles/trade:1m:tBTCUSD/hist",
             params={"limit": str(limit), "sort": "1"})
    arr = r.json()
    data = []
    for k in arr[-limit:]:
        t, o, c, h, l, v = k
        data.append({
            "time": datetime.fromtimestamp(int(t)/1000, tz=timezone.utc),
            "open": float(o), "high": float(h), "low": float(l), "close": float(c),
            "volume": float(v)
        })
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("time").reset_index(drop=True)
    return df

def _ohlc_coinbase(limit=240):
    # returns [[time, low, high, open, close, volume], ...] (time is seconds)
    r = _req("https://api.exchange.coinbase.com/products/BTC-USD/candles",
             params={"granularity": "60"})
    rows = r.json()
    # به‌صورت صعودی بر اساس زمان
    rows = sorted(rows, key=lambda x: x[0])[-limit:]
    data = []
    for t, lo, hi, o, c, v in rows:
        data.append({
            "time": datetime.fromtimestamp(int(t), tz=timezone.utc),
            "open": float(o), "high": float(hi), "low": float(lo), "close": float(c),
            "volume": float(v)
        })
    df = pd.DataFrame(data)
    return df

def _pick_first_nonempty(dfs):
    for df in dfs:
        if df is not None and not df.empty:
            return df
    return None

def _fetch_ohlcv_from_providers(limit=240):
    errors = []
    for fn in (_ohlc_kraken, _ohlc_bitfinex, _ohlc_coinbase):
        try:
            df = fn(limit=limit)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            errors.append(str(e))
    raise RuntimeError("Failed to fetch OHLCV from all providers: " + " | ".join(errors))

def get_recent_minutes(limit=240):
    """OHLCV با کش داخلی و fallback چندمنبعی."""
    now = time.time()
    if _OHLCV_CACHE["df"] is not None and (now - _OHLCV_CACHE["ts"] < OHLCV_CACHE_SECONDS):
        # از کش برگردان، ولی برش آخر limit رو بده
        df = _OHLCV_CACHE["df"].tail(limit).copy()
        return df

    df = _fetch_ohlcv_from_providers(limit=limit)
    # کش کن (با نسخه کامل تا دفعات بعد نیاز نباشه دوباره بگیریم)
    _OHLCV_CACHE["df"] = df.copy()
    _OHLCV_CACHE["ts"] = now
    return df.tail(limit).copy()
