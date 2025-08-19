import pandas as pd
import matplotlib.pyplot as plt
import psycopg2

conn = psycopg2.connect(**DB_CONFIG)
df = pd.read_sql("SELECT timestamp, entry_price, last_price, amount FROM positions WHERE status='closed'", conn)
df['pnl'] = (df['last_price'] - df['entry_price']) * df['amount']
df['cumulative_pnl'] = df['pnl'].cumsum()

plt.plot(df['timestamp'], df['cumulative_pnl'])
plt.title("Cumulative PnL Over Time")
plt.xlabel("Time")
plt.ylabel("USD Profit")
plt.show()
