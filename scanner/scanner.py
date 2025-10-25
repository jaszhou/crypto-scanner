import ccxt
import pandas as pd
# import talib
import requests
import mplfinance as mpf
import tempfile
import os
import psycopg2
import time
from datetime import datetime
import pytz
import functools
from dotenv import load_dotenv
from market import get_market_indicator
from get_list import *
import schedule

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
THRESHOLD = float(os.getenv("THRESHOLD", 1.0))

TRAILING_STOP_PCT = float(os.getenv("TRAILING_STOP_PCT", 5)) # Default to 5% if not set
NUM_SYMBOLS = int(os.getenv("NUM_SYMBOLS", 30))  # Default to 30 if not set
PROFIT_TARGET_PCT = float(os.getenv("PROFIT_TARGET_PCT", 10))  # Default to 10% if not set
# import os
# import ccxt
# import psycopg2

TRADING_MODE = os.environ.get("TRADING_MODE", "paper")
TRADE_AMOUNT_USD = float(os.environ.get("TRADE_AMOUNT_USD", 50))
TRADE_MAX = int(os.environ.get("TRADE_MAX", 5)) # maximum number of trades

# Initialize exchange for live trading
exchange_live = None
if TRADING_MODE == "live":
    exchange_live = ccxt.binance({
        "apiKey": os.environ.get("BINANCE_API_KEY"),
        "secret": os.environ.get("BINANCE_SECRET_KEY"),
        "enableRateLimit": True,
    })

def sydney_time():
    return datetime.now(pytz.timezone('Australia/Sydney')).strftime('%Y-%m-%d %H:%M:%S')

def sydney_time_logger(func):
    """A decorator to log function execution time with Sydney timestamps."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"[{sydney_time()}] --- Entering {func.__name__} ---")
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"[{sydney_time()}] --- Exiting {func.__name__}. Execution time: {end_time - start_time:.3f}s ---")
        return result
    return wrapper

# Function to place order with logging
@sydney_time_logger
def place_order(symbol, side, amount):
    start_time = time.time()
    print(f"🔧 DEBUG: place_order called with symbol={symbol}, side={side}, amount={amount}")
    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
    
        if side == "sell":
            # Update position with exit price
            update_position_exit(symbol, price)
        else:
            save_position(symbol, side, amount, price)
        
        if TRADING_MODE == "paper":

            print(f"📄 Paper trade: {side} {amount:.6f} {symbol} at {price}")


            return {"status": "paper"}
        else:
            try:
                order = exchange_live.create_market_order(symbol, side, amount)

                print(f"✅ Live trade executed: {side} {amount:.6f} {symbol} at {price}")
                return order
            except Exception as e:
                print(f"❌ Trade failed: {e}")
                return None
    finally:
        print(f"⏱️ place_order took {time.time() - start_time:.3f}s")
        msg = f"📊 {symbol}\n {side}"
        send_telegram_text(msg)


# Save position to Postgres
def save_position(symbol, side, amount, entry_price):
    start_time = time.time()
    print(f"🔧 DEBUG: save_position called with symbol={symbol}, side={side}, amount={amount}, entry_price={entry_price}")
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
    finally:
        print(f"⏱️ save_position took {time.time() - start_time:.3f}s")

# Update position with exit price for paper trading
def update_position_exit(symbol, exit_price):
    start_time = time.time()
    print(f"🔧 DEBUG: update_position_exit called with symbol={symbol}, exit_price={exit_price}")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            UPDATE positions SET last_price=%s, side='sale', status='closed' 
            WHERE symbol=%s AND status='open'
        """, (exit_price, symbol))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Position exit update error: {e}")
    finally:
        print(f"⏱️ update_position_exit took {time.time() - start_time:.3f}s")

# Check open positions for exit rules
@sydney_time_logger
def get_open_positions():
    start_time = time.time()
    print(f"🔧 DEBUG: get_open_positions called")
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
    finally:
        print(f"⏱️ get_open_positions took {time.time() - start_time:.3f}s")

def has_open_position(symbol):
    start_time = time.time()
    print(f"🔧 DEBUG: has_open_position called with symbol={symbol}")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        # Check for open positions or if a trade for this symbol has already been made today
        cur.execute("SELECT COUNT(*) FROM positions WHERE symbol=%s AND (status='open' OR timestamp::date = CURRENT_DATE)", (symbol,))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count > 0
    except Exception as e:
        print(f"❌ Failed to check position for {symbol}: {e}")
        return False
    finally:
        print(f"⏱️ has_open_position took {time.time() - start_time:.3f}s")

@sydney_time_logger
def has_open_coin():
    start_time = time.time()
    print("🔧 DEBUG: has_open_position called ")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        # Check for open positions or if a trade for this symbol has already been made today
        cur.execute("SELECT COUNT(*) FROM positions WHERE status='open'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except Exception as e:
        print(f"❌ Failed to check position for {symbol}: {e}")
        return False
    finally:
        print(f"⏱️ has_open_position took {time.time() - start_time:.3f}s")

exchange = ccxt.binance()

# ------------------ TELEGRAM ------------------
def send_telegram_text(msg):
    start_time = time.time()
    print(f"🔧 DEBUG: send_telegram_text called with msg length={len(msg)}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    print(f"⏱️ send_telegram_text took {time.time() - start_time:.3f}s")

def send_telegram_chart(image_path, caption=""):
    start_time = time.time()
    print(f"🔧 DEBUG: send_telegram_chart called with image_path={image_path}, caption={caption}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(image_path, "rb") as img:
        files = {"photo": img}
        data = {"chat_id": CHAT_ID, "caption": caption}
        requests.post(url, files=files, data=data)
    print(f"⏱️ send_telegram_chart took {time.time() - start_time:.3f}s")

# ------------------ DATABASE ------------------
def save_to_postgres(symbol, rsi=None, macd=None, sig=None, golden_cross=None, signals=None, close_price=None):
    start_time = time.time()
    # print(f"🔧 DEBUG: save_to_postgres called with symbol={symbol}, rsi={rsi}, signals={signals}")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Handle optional parameters. psycopg2 converts None to NULL.
        db_rsi = float(rsi) if rsi is not None else None
        db_macd = float(macd) if macd is not None else None
        db_sig = float(sig) if sig is not None else None
        db_golden_cross = bool(golden_cross) if golden_cross is not None else None
        db_signals = ", ".join(signals) if signals else ""
        db_close_price = float(close_price) if close_price is not None else None

        cur.execute("""
            INSERT INTO crypto_signals 
            (symbol, rsi, macd, macd_signal, golden_cross, signals, close_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (symbol, db_rsi, db_macd, db_sig, db_golden_cross, db_signals, db_close_price))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ DB Error for {symbol}: {e}")
    # finally:
    #     print(f"⏱️ save_to_postgres took {time.time() - start_time:.3f}s")


def update_future_returns():
    start_time = time.time()
    print(f"🔧 DEBUG: update_future_returns called")
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
    finally:
        print(f"⏱️ update_future_returns took {time.time() - start_time:.3f}s")

# ------------------ UTILS ------------------
def percent_change(open_price, close_price):
    return (close_price - open_price) / open_price * 100

def check_golden_cross(df, short=50, long=200):
    df["ema_short"] = df["close"].ewm(span=short).mean()
    df["ema_long"] = df["close"].ewm(span=long).mean()
    return df["ema_short"].iloc[-1] > df["ema_long"].iloc[-1]


def plot_chart(df, symbol):
    df_plot = df.copy()
    df_plot.index = pd.to_datetime(df_plot['timestamp'], unit='ms')
    df_plot = df_plot[['open','high','low','close','volume']]
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    mpf.plot(df_plot.tail(30), type='candle', volume=True, style='yahoo',
             title=f"{symbol} - Last 30 Days", mav=(9,21,50), savefig=temp_file.name)
    return temp_file.name

def get_top_usdt_symbols(limit=50):
    start_time = time.time()
    print(f"🔧 DEBUG: get_top_usdt_symbols called with limit={limit}")
    exchange.load_markets()
    usdt_pairs = [s for s in exchange.symbols if s.endswith("/USDT")]
    tickers = exchange.fetch_tickers()
    volume_data = [(s, tickers[s]["quoteVolume"]) for s in usdt_pairs if s in tickers and "quoteVolume" in tickers[s]]
    top_symbols = sorted(volume_data, key=lambda x: x[1], reverse=True)[:limit]
    print(f"⏱️ get_top_usdt_symbols took {time.time() - start_time:.3f}s")
    return [s[0] for s in top_symbols]

def get_top_market_cap_symbols_db():
    """Fetch top 20 cryptocurrencies by market cap and save to database"""
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 20,
            "page": 1
        }
        response = requests.get(url, params=params)
        data = response.json()

        top_20 = [
            {
                'rank': coin['market_cap_rank'],
                'symbol': coin['symbol'].upper(),
                'name': coin['name'],
                'price': coin['current_price'],
                'market_cap': coin['market_cap'],
                'volume': coin['total_volume']
            }
            for coin in data
        ]

        
        # Save to database
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        for rank, item in enumerate(top_20, 1):
            cur.execute("""
                INSERT INTO market_caps (symbol, market_cap, rank)
                VALUES (%s, %s, %s)
            """, (item['symbol'], item['market_cap'], rank))
        conn.commit()
        cur.close()
        conn.close()
        
        return [item['symbol'] for item in top_20]
    except Exception as e:
        print(f"❌ Failed to fetch market caps: {e}")
        return []

def get_top_market_cap_symbols():
    """Fetch top 20 cryptocurrencies by market cap and save to database"""
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 20,
            "page": 1
        }
        response = requests.get(url, params=params)
        data = response.json()

        top_20 = [
            {
                'rank': coin['market_cap_rank'],
                'symbol': coin['symbol'].upper(),
                'name': coin['name'],
                'price': coin['current_price'],
                'market_cap': coin['market_cap'],
                'volume': coin['total_volume']
            }
            for coin in data
        ]
        
        exchange.load_markets()
        usdt_pairs = [s for s in exchange.symbols if s.endswith("/USDT")]

        return [f"{item['symbol']}/USDT" for item in top_20]
    except Exception as e:
        print(f"❌ Failed to fetch market caps: {e}")
        return []
    
def get_ohlcv(symbol, timeframe='1d', limit=10):
    """Fetch OHLCV and return a pandas DataFrame."""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    # ccxt returns [timestamp, open, high, low, close, volume]
    df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('date', inplace=True)
    return df[['open','close','volume','high','low','timestamp']]

def check_buy_signal(df):
    """Add columns and return the last row with buy signal status."""
    df = df.copy()
    df['price_change'] = df['close'] - df['open']
    df['price_change_pct'] = (df['price_change'] / df['open']) * 100
    df['up'] = df['price_change'] > 0
    df['prev_up'] = df['up'].shift(1)

    df['volume_change'] = df['volume'].pct_change()
    df['prev_volume_change'] = df['volume_change'].shift(1)

    df['buy_signal'] = (
        (df['up']) &
        (df['prev_up']) &
        (df['price_change_pct'] > 2.0) &
        (df['volume_change'] > 0) & 
        (df['prev_volume_change'] > 0)
    )
    return df

@sydney_time_logger
def scan_symbols_last_day(num_symbols=10):
    start_time = time.time()
    print(f"🔧 DEBUG: scan_symbols called")
    # SYMBOLS = fetch_binance_marketcap_top20(num_symbols)['symbol_pair'].tolist()

    SYMBOLS = get_top_usdt_symbols(num_symbols)

    # SYMBOLS = get_top_market_cap_symbols()


    print(f"🔧 DEBUG: Top symbols by market cap: {SYMBOLS}")
    alerts = []


    timeframe = '1h'      # hourly candles
    limit = 30            # how many candles to fetch

    buy_signals_today = []

    for sym in SYMBOLS:
        df = get_ohlcv(sym, timeframe=timeframe, limit=limit)

        # ohlcv = exchange.fetch_ohlcv(sym, timeframe=timeframe, limit=limit)
        # df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # print(f"DEBUG: {sym} df.head(5):")
        # print(df.head(5))

        df = check_buy_signal(df)
        if df['buy_signal'].iloc[-1]:
            buy_signals_today.append(sym)
            alerts.append((sym, df))
            print(f"✅ Buy signal for {sym} on {df.index[-1].date()}")

    if buy_signals_today:
        print("✅ Buy signals detected today for:", ", ".join(buy_signals_today))
    else:
        print("❌ No buy signals today.")

    print(f"⏱️ scan_symbols took {time.time() - start_time:.3f}s")
    return alerts

# ------------------ MAIN SCAN ------------------
def scan_symbols(num_symbols=10):
    start_time = time.time()
    print(f"🔧 DEBUG: scan_symbols called")
    SYMBOLS = get_top_usdt_symbols(num_symbols)
    alerts = []
    for sym in SYMBOLS:
        try:
            ohlcv = exchange.fetch_ohlcv(sym, '1h', limit=250)
            df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
            # df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            # macd, macdsignal, _ = talib.MACD(df['close'], 12,26,9)
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
    print(f"⏱️ scan_symbols took {time.time() - start_time:.3f}s")
    return alerts

def add_indicators(df):
    # Ensure we have the right column name
    if 'Close' in df.columns:
        df['close'] = df['Close']
    
    # EMA50 / EMA200
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14, min_periods=14).mean()
    avg_loss = loss.rolling(window=14, min_periods=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # MACD & Signal
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

    return df

@sydney_time_logger
def check_exit_signals(df, entry_price, last_price, sym, amount, entry_time):
    signals = []
    df = add_indicators(df)

    # --- Risk Management: Stop Loss ---
    # profit_pct = (last_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
    # if profit_pct <= -5:
    #     signals.append("Stop Loss Hit (-5%)")

    if profit_pct > PROFIT_TARGET_PCT:
        signals.append(f"Profit Hit ({profit_pct:.2f}%)")

    # --- Technical Selling Signals ---
    # if df['ema50'].iloc[-1] < df['ema200'].iloc[-1] and df['ema50'].iloc[-2] >= df['ema200'].iloc[-2]:
    #     signals.append("Death Cross (SELL)")
    # if df['rsi'].iloc[-1] > 70 and df['rsi'].iloc[-1] < df['rsi'].iloc[-2]:
    #     signals.append("RSI Overbought (SELL)")
    # if df['macd'].iloc[-1] < df['signal'].iloc[-1] and df['macd'].iloc[-2] >= df['signal'].iloc[-2]:
    #     signals.append("MACD Bearish Crossover (SELL)")

    # --- Trailing Stop: Use max of last 5 close prices ---
    recent_high = df['close'].tail(5).max()
    
    
    print(f"🔍 {sym} max of last 5 closes: {recent_high}, last price: {last_price}")
    if last_price < recent_high * (1 - TRAILING_STOP_PCT / 100):
        signals.append("Trailing Stop Triggered (SELL)")

    # --- Place order if any exit condition is met ---
    if signals:
        place_order(sym, "sell", amount)

    return signals

def health_check():
    """
    Send market indicators to Telegram every hour
    Returns True if successful, False otherwise
    """
    try:
        # Get market indicators
        indicators = get_market_indicator()
        
        # Format message with timestamp
        msg = f"🔄 Hourly Health Check - {sydney_time()}\n"
        msg += f"Market Indicators:\n{indicators}"
        
        # Send to Telegram
        send_telegram_text(msg)
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

# ------------------ RUN LOOP ------------------
if __name__ == "__main__":

    # Print .env file variables
    print("=== .env Variables ===")
    env_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASS', 'TELEGRAM_TOKEN', 'CHAT_ID', 'THRESHOLD']
    for var in env_vars:
        value = os.getenv(var, 'NOT SET')
        print(f"{var}={value}")
    print("=====================")

    last_future_update = 0

    # Run immediately on startup
    health_check()
    
    # Schedule hourly runs
    schedule.every().hour.do(health_check)

    while True:  # Ensure minimum balance to trade

        schedule.run_pending()

        # buying condition
        if has_open_coin() < TRADE_MAX and get_USDT_balance() > TRADE_AMOUNT_USD:

            alerts = scan_symbols_last_day(NUM_SYMBOLS)

            for sym, df in alerts:
                
                close_price = df['close'].iloc[-1]
                save_to_postgres(sym, close_price)

                # Strong signals only
                if get_market_indicator():
                # if True:
                    # Check if already holding position
                    if has_open_position(sym):
                        print(f"⚠️ Already holding position for {sym}, skipping buy signal")
                        continue

                    print(f"📊 {sym}\n")

                    msg = f"📊 {sym}\nBuying..price: {close_price}.\n"
                    # msg = f"📊 {sym} \n Buying..price: {close_price} open: {open}, close: {close_price}, change: {price_change:.2f}, up: {up}, prev_up: {prev_up}, volume: {volume:.2f}, vol_change: {volume_change:.2f}, prev_vol_change: {prev_volume_change:.2f}\n"


                    print(df)
                    chart_path = plot_chart(df, sym)
                    send_telegram_chart(chart_path, caption=f"{sym} Chart")
                
                    send_telegram_text(msg)
                    # os.remove(chart_path)

                    # Determine trade amount in base currency
                    ticker = exchange.fetch_ticker(sym)
                    price = ticker['last']

                    flow_num = get_flow_balance()
                    
                    TRADE_AMOUNT_USD = flow_num * 10 if flow_num else TRADE_AMOUNT_USD 
                    amount = TRADE_AMOUNT_USD / price

                    # Place buy order
                    place_order(sym, "buy", amount)
        else:
            print(f"⚠️ Maximum open trades reached ({TRADE_MAX}), skipping buy signals  this cycle.")
            

        # Check for exit conditions
        positions = get_open_positions()
        for pos_id, sym, side, entry_price, amount in positions:
                
            # Get fresh data for exit analysis
            try:
                ohlcv = exchange.fetch_ohlcv(sym, '1d', limit=30)
                df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
                ticker = exchange.fetch_ticker(sym)
                last_price = ticker['last']
                profit_pct = (last_price - entry_price)/entry_price*100 if entry_price > 0 else 0

                print(f"🔍 Checking exit for {sym}: Entry={entry_price}, Last={last_price}, Profit={profit_pct:.2f}%")
                signals = check_exit_signals(df, entry_price, last_price, sym, amount, entry_time=None)
            except Exception as e:
                print(f"❌ Error getting data for {sym}: {e}")
                continue
            if signals:
                msg = f"📊 {sym}\nSignals: {', '.join(signals)}\nSelling... Entry={entry_price}, Last={last_price}, Profit={profit_pct:.2f}%" 
                send_telegram_text(msg)
                chart_path = plot_chart(df, sym)    
                send_telegram_chart(chart_path, caption=f"{sym} Chart")

                # Place sell order 
                place_order(sym, "sell", amount)


        # Wait 10 minutes before next scan
        print(f"⏳ Waiting 300 seconds...")
        time.sleep(300)