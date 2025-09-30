import ccxt
import time
import requests
import os
from datetime import datetime

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
THRESHOLD = float(os.getenv("THRESHOLD", 1.0))

TRAILING_STOP_PCT = float(os.getenv("TRAILING_STOP_PCT", 5)) # Default to 5% if not set
NUM_SYMBOLS = int(os.getenv("NUM_SYMBOLS", 30))  # Default to 30 if not set
PROFIT_TARGET_PCT = float(os.getenv("PROFIT_TARGET_PCT", 10))  # Default to 10% if not set
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


def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

# 🔹 Binance connection
exchange = ccxt.binance()

def get_usdt_pairs():
    markets = exchange.load_markets()
    return {symbol for symbol in markets.keys() if symbol.endswith("/USDT")}

def get_pair_info(symbol: str):
    """
    Fetches detailed info about a trading pair (status, base asset, quote asset, etc.)
    """
    info = exchange.publicGetExchangeInfo()
    for s in info["symbols"]:
        if s["symbol"] == symbol.replace("/", ""):  # e.g. BTC/USDT → BTCUSDT
            return {
                "symbol": symbol,
                "status": s["status"],  # TRADING, PENDING_TRADING, etc.
                "baseAsset": s["baseAsset"],
                "quoteAsset": s["quoteAsset"],
                "permissions": s.get("permissions", [])
            }
    return None

# Initial snapshot
old_pairs = get_usdt_pairs()
print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Initial number of USDT pairs: {len(old_pairs)}")

while True:
    time.sleep(300)  # check every 60 seconds
    new_pairs = get_usdt_pairs()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Current number of USDT pairs: {len(new_pairs)}")

    added = new_pairs - old_pairs


    if added:
        for pair in added:
            info = get_pair_info(pair)
            if info:
                msg = (
                    f"🆕 New USDT Pair Listed on Binance!\n"
                    f"• Symbol: {info['symbol']}\n"
                    f"• Base Asset: {info['baseAsset']}\n"
                    f"• Quote Asset: {info['quoteAsset']}\n"
                    f"• Status: {info['status']}\n"
                    f"• Permissions: {', '.join(info['permissions'])}"
                )
            else:
                msg = f"🆕 New USDT Pair: {pair} (details not available yet)"
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
            send_telegram_message(msg)


    old_pairs = new_pairs
