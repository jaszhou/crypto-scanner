import ccxt
import pandas as pd
import talib
import requests
import mplfinance as mpf
import tempfile
import os
import psycopg2
import time
from dotenv import load_dotenv

load_dotenv()  # Loads .env file

# ------------------ CONFIG ------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "port": 5432
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
THRESHOLD = float(os.getenv("THRESHOLD", "1.0"))

# import os
# import ccxt
# import psycopg2

TRADING_MODE = os.environ.get("TRADING_MODE", "paper")
TRADE_AMOUNT_USD = float(os.environ.get("TRADE_AMOUNT_USD", 50))

# Initialize exchange for live trading
exchange_live = None
if TRADING_MODE == "live":
    exchange_live = ccxt.binance({
        "apiKey": os.environ.get("BINANCE_API_KEY"),
        "secret": os.environ.get("BINANCE_SECRET_KEY"),
        "enableRateLimit": True,
    })

# Function to place order
def place_order(symbol, side, amount):
    if TRADING_MODE == "paper":
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        print(f"📄 Paper trade: {side} {amount:.6f} {symbol} at {price}")
        if side == "sell":
            # Update position with exit price
            update_position_exit(symbol, price)
        else:
            save_position(symbol, side, amount, price)
        return {"status": "paper"}
    else:
        try:
            order = exchange_live.create_market_order(symbol, side, amount)
            entry_price = float(order['fills'][0]['price'])
            save_position(symbol, side, amount, entry_price)
            print(f"✅ Live trade executed: {side} {amount:.6f} {symbol} at {entry_price}")
            return order
        except Exception as e:
            print(f"❌ Trade failed: {e}")
            return None

# Save position to Postgres
def save_position(symbol, side, amount, entry_price):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO positions (symbol, side, entry_price, amount)
            VALUES (%s, %s, %s, %s)
        """, (symbol, side, entry_price, amount))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Position DB error: {e}")

# Update position with exit price for paper trading
def update_position_exit(symbol, exit_price):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            UPDATE positions SET last_price=%s, status='closed' 
            WHERE symbol=%s AND status='open'
        """, (exit_price, symbol))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Position exit update error: {e}")

# Check open positions for exit rules
def get_open_positions():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT id, symbol, side, entry_price, amount FROM positions WHERE status='open'")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ Failed to fetch positions: {e}")
        return []


exchange = ccxt.binance()

# ------------------ TELEGRAM ------------------
def send_telegram_text(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def send_telegram_chart(image_path, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(image_path, "rb") as img:
        files = {"photo": img}
        data = {"chat_id": CHAT_ID, "caption": caption}
        requests.post(url, files=files, data=data)

# ------------------ DATABASE ------------------
def save_to_postgres(symbol, surge, rsi, macd, sig, golden_cross, signals, close_price):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO crypto_signals 
            (symbol, surge, rsi, macd, macd_signal, golden_cross, signals, close_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (symbol, float(surge), float(rsi), float(macd), float(sig), bool(golden_cross), ", ".join(signals), float(close_price)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ DB Error for {symbol}: {e}")

def update_future_returns():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, symbol, timestamp, close_price
            FROM crypto_signals
            WHERE future_24h IS NULL;
        """)
        rows = cur.fetchall()
        for row in rows:
            sig_id, symbol, ts, entry_price = row
            ohlcv = exchange.fetch_ohlcv(symbol, '1h', since=int(ts.timestamp() * 1000), limit=30)
            if not ohlcv: 
                continue
            df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            future_6h = float(df['close'].iloc[6]) if len(df) > 6 else None
            future_24h = float(df['close'].iloc[24]) if len(df) > 24 else None
            return_6h = float((future_6h - entry_price)/entry_price*100) if future_6h else None
            return_24h = float((future_24h - entry_price)/entry_price*100) if future_24h else None
            cur.execute("""
                UPDATE crypto_signals
                SET future_6h=%s, future_24h=%s, return_6h=%s, return_24h=%s
                WHERE id=%s
            """, (future_6h, future_24h, return_6h, return_24h, sig_id))
            conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Future return update error: {e}")

# ------------------ UTILS ------------------
def percent_change(open_price, close_price):
    return (close_price - open_price) / open_price * 100

def check_golden_cross(df, short=50, long=200):
    df["ema_short"] = df["close"].ewm(span=short).mean()
    df["ema_long"] = df["close"].ewm(span=long).mean()
    return df["ema_short"].iloc[-1] > df["ema_long"].iloc[-1]

def plot_chart(df, symbol):
    df_plot = df.copy()
    df_plot.index = pd.to_datetime(df_plot['time'], unit='ms')
    df_plot = df_plot[['open','high','low','close','volume']]
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    mpf.plot(df_plot.tail(80), type='candle', volume=True, style='yahoo',
             title=f"{symbol} - Last 80 Hours", mav=(9,21,50), savefig=temp_file.name)
    return temp_file.name

def get_top_usdt_symbols(limit=50):
    exchange.load_markets()
    usdt_pairs = [s for s in exchange.symbols if s.endswith("/USDT")]
    tickers = exchange.fetch_tickers()
    volume_data = [(s, tickers[s]["quoteVolume"]) for s in usdt_pairs if s in tickers and "quoteVolume" in tickers[s]]
    top_symbols = sorted(volume_data, key=lambda x: x[1], reverse=True)[:limit]
    return [s[0] for s in top_symbols]

# ------------------ MAIN SCAN ------------------
def scan_symbols():
    SYMBOLS = get_top_usdt_symbols(10)
    alerts = []
    for sym in SYMBOLS:
        try:
            ohlcv = exchange.fetch_ohlcv(sym, '1h', limit=250)
            df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            macd, macdsignal, _ = talib.MACD(df['close'], 12,26,9)
            surge = percent_change(df['open'].iloc[-1], df['close'].iloc[-1])
            rsi_val = df['rsi'].iloc[-1]
            macd_val, sig_val = macd.iloc[-1], macdsignal.iloc[-1]
            golden_cross = check_golden_cross(df)
            triggered = []
            if surge >= THRESHOLD:
                triggered.append(f"🚀 Surge +{surge:.2f}%")
            if rsi_val > 55: 
                triggered.append(f"RSI {rsi_val:.1f}")
            if macd_val > sig_val:
                triggered.append("MACD Bullish")
            if golden_cross:
                triggered.append("Golden Cross")
            if triggered:
                alerts.append((sym, triggered, surge, rsi_val, macd_val, sig_val, golden_cross, df))
        except Exception:
            continue
    return alerts

# ------------------ RUN LOOP ------------------
if __name__ == "__main__":

    # Print .env file variables
    print("=== .env Variables ===")
    env_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASS', 'TELEGRAM_TOKEN', 'CHAT_ID', 'THRESHOLD']
    for var in env_vars:
        value = os.getenv(var, 'NOT SET')
        print(f"{var}={value}")
    print("=====================")

    while True:
        alerts = scan_symbols()

        for sym, signals, surge, rsi_val, macd_val, sig_val, golden_cross, df in alerts:
            
            close_price = df['close'].iloc[-1]
            save_to_postgres(sym, surge, rsi_val, macd_val, sig_val, golden_cross, signals, close_price)

            # Strong signals only
            if len(signals) >= 2 and surge >= THRESHOLD:

                print(f"📊 {sym}\nSignals: {', '.join(signals)}\nRSI: {rsi_val:.2f}\nMACD: {macd_val:.5f} | Signal: {sig_val:.5f}\n1h Change: {surge:.2f}%")

                msg = f"📊 {sym}\nSignals: {', '.join(signals)}\nRSI: {rsi_val:.2f}\nMACD: {macd_val:.5f} | Signal: {sig_val:.5f}\n1h Change: {surge:.2f}%"
                send_telegram_text(msg)
                chart_path = plot_chart(df, sym)
                send_telegram_chart(chart_path, caption=f"{sym} Chart")
                # os.remove(chart_path)

                # Determine trade amount in base currency
                ticker = exchange.fetch_ticker(sym)
                price = ticker['last']
                amount = TRADE_AMOUNT_USD / price

                # Place buy order
                place_order(sym, "buy", amount)
        
        # Update future returns
        update_future_returns()

        # Check for exit conditions
        positions = get_open_positions()
        for pos_id, sym, side, entry_price, amount in positions:
            ticker = exchange.fetch_ticker(sym)
            last_price = ticker['last']
            profit_pct = (last_price - entry_price)/entry_price*100 if entry_price > 0 else 0
            # Example exit: +2% profit or -1% loss
            if profit_pct >= 0.1 or profit_pct <= -1:
                place_order(sym, "sell", amount)
                # Update status in DB
                try:
                    conn = psycopg2.connect(**DB_CONFIG)
                    cur = conn.cursor()
                    cur.execute("UPDATE positions SET status='closed' WHERE id=%s", (pos_id,))
                    conn.commit()
                    cur.close()
                    conn.close()
                except Exception as e:
                    print(f"❌ Failed to close position: {e}")


        # Wait 10 minutes before next scan
        print(f"⏳ Waiting 60 seconds...")
        time.sleep(60)
