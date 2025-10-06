import os
from dotenv import load_dotenv
from scanner import get_top_market_cap_symbols
import psycopg2

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "port": 5432
}

def main():
    print("Fetching top 20 cryptocurrencies by market cap...")
    top_symbols = get_top_market_cap_symbols()
    
    if top_symbols:
        print("Successfully fetched and saved top market cap symbols:")
        for i, symbol in enumerate(top_symbols, 1):
            print(f"{i}. {symbol}")
    else:
        print("Failed to fetch market cap data")

if __name__ == "__main__":
    main()