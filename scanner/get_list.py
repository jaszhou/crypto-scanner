from binance.client import Client
import pandas as pd
import os
import csv
import time
# import logging
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException


api_key = os.environ.get('binance_api')
api_secret = os.environ.get('binance_secret')


client = Client(api_key, api_secret)





def get_usdt_pairs(num=50):


    symbols = client.get_ticker()

    
    df = pd.DataFrame(symbols)
    df = df[df.symbol.str.endswith('USDT')]

    df = df[~df.symbol.str.contains('DOWN')]
    df = df[~df.symbol.str.contains('UP')]
    df = df[~df.symbol.str.startswith('USD')] # remove USD* pairs



    df = df.astype({'volume':'float'})
    df = df.astype({'lastPrice':'float'})
    df['v'] = df['volume'] * df['lastPrice']

    # print(df.iloc[1])

    # df = df.sort_values(by="volume", ascending=False)
    df = df.sort_values(by="v", ascending=False)

    # print(df.head(num))
    # logging.info(df.head(num))
    
    df = df['symbol']
    df.head(num).to_csv('trade_pair.csv', index=False)
    # print(df.head(num))

    

def retry(fun, max_tries=10):
    for i in range(max_tries):
        try:
           time.sleep(1) 
           return fun()
           break
        except Exception:
            continue

def get_gainer():

    get_usdt_pairs(num=20)


def get_flow_balance():
    balance = client.get_asset_balance(asset="FLOW")
    balance = float(balance['free'])
    # print(bnb_balance)
    return balance

def get_icp_balance():
    balance = client.get_asset_balance(asset="ICP")
    balance = float(balance['free'])
    # print(bnb_balance)
    return balance

def get_balance(symbol):
    balance = client.get_asset_balance(asset=symbol)
    balance = float(balance['free'])
    # print(bnb_balance)
    return balance

def get_USDT_balance():
    balance = client.get_asset_balance(asset='USDT')
    balance = float(balance['free'])
    # print(bnb_balance)
    return balance

def get_balance_all(symbol):
    balance = client.get_asset_balance(asset=symbol)
    balance = float(balance['locked']) + float(balance['free'])
    # print(bnb_balance)
    return balance

#price = client.get_symbol_ticker(symbol=pair)
def get_symbol_ticker(symbol):
    tries = 5
    price = {}

    for i in range(tries):
              try:
                 # do stuff
                 price = client.get_symbol_ticker(symbol)
              except:
                 time.sleep(1)
                 continue
              break
    return price


def get_trend(pair):
    # klines = client.get_historical_klines(pair, Client.KLINE_INTERVAL_15MINUTE, "15 minute ago UTC")
    klines = client.get_historical_klines(pair, Client.KLINE_INTERVAL_1HOUR, "1 hour ago UTC")
    
    # print(klines)

    for line in klines:
        del line[6:]

    df = pd.DataFrame(klines, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    last_row_df = df.iloc[-1:]

    # close = float(last_row_df['close'])

    open = float(last_row_df['open'].iloc[0])
    close = float(last_row_df['close'].iloc[0])

    # print(f"open: {open}")

    if (close - open) > 0 :
        # print("up")
        return "up"
    else :
        # print("down")
        return "down"

    # balance = client.get_asset_balance(asset=symbol)
    # balance = float(balance['free'])
    # # print(bnb_balance)
    # return balance

# get_gainer()    

#get_usdt_pairs()
# print("flow balance is: {b}".format(b=get_USDT_balance()))

# get_trend("RAREUSDT")

# print(get_trend("BNBUSDT"))

# p=get_symbol_ticker("RAREUSDT")

if __name__ == "__main__":
    # get_gainer()
    print( "USDT balance is: {b}".format(b=get_USDT_balance()) )
    get_flow_balance()