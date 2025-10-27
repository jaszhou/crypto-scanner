import time
import pandas as pd
import requests

# List of major cryptos to monitor
major_cryptos = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "XRPUSDT"]

# Binance API endpoint (public, no auth required)
BINANCE_URL = "https://api.binance.com/api/v3/klines"

def get_crypto_data(symbol, interval="15m", limit=100):
    """Fetch OHLCV data from Binance"""
    url = f"{BINANCE_URL}?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume","close_time",
        "qav","trades","taker_base_vol","taker_quote_vol","ignore"
    ])
    df["close"] = df["close"].astype(float)
    return df

def compute_indicators(df):
    """Add EMA and RSI indicators"""
    df["ema20"] = df["close"].ewm(span=20).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()

    # RSI (14)
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    return df

def detect_buy_signal(df):
    """Buy if EMA20 > EMA50 and RSI < 70"""
    return (df["ema20"].iloc[-1] > df["ema50"].iloc[-1]) and (df["rsi"].iloc[-1] < 70)

def  get_market_indicator():
    while True:
        signals = {}
        bullish_count = 0

        for sym in major_cryptos:
            df = get_crypto_data(sym, interval="1h", limit=100)
            df = compute_indicators(df)
            last_price = df["close"].iloc[-1]

            if detect_buy_signal(df):
                signals[sym] = f"BUY ✅ ({last_price:.2f})"
                bullish_count += 1
            else:
                signals[sym] = f"HOLD ⚪ ({last_price:.2f})"

        # Print dashboard
        print("\n--- Market Signal Dashboard ---")
        for sym, sig in signals.items():
            print(f"{sym}: {sig}")
        print(f"Overall: {bullish_count}/{len(major_cryptos)} showing BUY")

        if bullish_count >= len(major_cryptos) * 0.7:
            print("🚀 Market is broadly bullish!")
            return True
        elif bullish_count <= len(major_cryptos) * 0.3:
            print("🔻 Market is broadly bearish!")
        else:
            print("🤔 Mixed signals across the market.")

        return False


        # time.sleep(60)  # refresh every 1 minute

# Run dashboard
is_bullish = get_market_indicator()
if is_bullish:
    print("Market is bullish, consider trading strategies.")