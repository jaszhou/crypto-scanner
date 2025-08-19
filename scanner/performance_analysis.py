import pandas as pd
import matplotlib.pyplot as plt
import psycopg2
import numpy as np
import os

# ------------------ CONFIG ------------------
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "dbname": os.environ.get("DB_NAME", "crypto_db"),
    "user": os.environ.get("DB_USER", "crypto_user"),
    "password": os.environ.get("DB_PASS", "crypto_pass"),
    "port": 5432
}

# ------------------ FETCH DATA ------------------
def fetch_positions():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        df = pd.read_sql("""
            SELECT symbol, side, entry_price, last_price, amount, timestamp
            FROM positions
            WHERE status='closed'
            ORDER BY timestamp
        """, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"❌ DB fetch error: {e}")
        return pd.DataFrame()

# ------------------ CALCULATE METRICS ------------------
def analyze_positions(df):
    if df.empty:
        print("No closed positions found.")
        return

    df['pnl'] = (df['last_price'] - df['entry_price']) * df['amount']
    df['percent_return'] = ((df['last_price'] - df['entry_price']) / df['entry_price']) * 100
    df['cumulative_pnl'] = df['pnl'].cumsum()

    total_trades = len(df)
    winning_trades = df[df['pnl'] > 0]
    losing_trades = df[df['pnl'] <= 0]
    win_rate = len(winning_trades) / total_trades * 100
    avg_profit = winning_trades['percent_return'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['percent_return'].mean() if not losing_trades.empty else 0
    total_profit = df['pnl'].sum()
    max_drawdown = (df['cumulative_pnl'].cummax() - df['cumulative_pnl']).max()

    print(f"Total trades: {total_trades}")
    print(f"Winning trades: {len(winning_trades)}")
    print(f"Losing trades: {len(losing_trades)}")
    print(f"Win rate: {win_rate:.2f}%")
    print(f"Average profit: {avg_profit:.2f}%")
    print(f"Average loss: {avg_loss:.2f}%")
    print(f"Cumulative PnL: ${total_profit:.2f}")
    print(f"Max Drawdown: ${max_drawdown:.2f}")

    return df

# ------------------ PLOT PNL ------------------
def plot_cumulative_pnl(df):
    if df.empty:
        return
    plt.figure(figsize=(12,6))
    plt.plot(df['timestamp'], df['cumulative_pnl'], label='Cumulative PnL', color='green')
    plt.title("Cumulative PnL Over Time")
    plt.xlabel("Time")
    plt.ylabel("USD Profit")
    plt.grid(True)
    plt.legend()
    plt.show()

# ------------------ PLOT HISTOGRAM ------------------
def plot_return_distribution(df):
    if df.empty:
        return
    plt.figure(figsize=(10,5))
    plt.hist(df['percent_return'], bins=30, color='skyblue', edgecolor='black')
    plt.title("Distribution of Trade Returns (%)")
    plt.xlabel("Return (%)")
    plt.ylabel("Number of Trades")
    plt.grid(True)
    plt.show()

# ------------------ MAIN ------------------
if __name__ == "__main__":
    positions_df = fetch_positions()
    analyzed_df = analyze_positions(positions_df)
    plot_cumulative_pnl(analyzed_df)
    plot_return_distribution(analyzed_df)
