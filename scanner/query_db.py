import psycopg2
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "port": 5432
}

def query_db(sql):
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

# Recent signals
print("=== Recent Signals ===")
recent = query_db("SELECT * FROM crypto_signals ORDER BY timestamp DESC LIMIT 10")
print(recent)

# High surge signals
print("\n=== High Surge Signals (>5%) ===")
high_surge = query_db("SELECT symbol, surge, rsi, signals, timestamp FROM crypto_signals WHERE surge > 5.0 ORDER BY timestamp DESC")
print(high_surge)

# Signals with returns
print("\n=== Signals with Returns ===")
returns = query_db("SELECT symbol, surge, return_6h, return_24h, timestamp FROM crypto_signals WHERE return_24h IS NOT NULL ORDER BY return_24h DESC")
print(returns)

# Count by symbol
print("\n=== Signal Count by Symbol ===")
counts = query_db("SELECT symbol, COUNT(*) as count FROM crypto_signals GROUP BY symbol ORDER BY count DESC")
print(counts)