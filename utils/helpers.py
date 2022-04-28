import pandas as pd
import math

def round_up(n, decimals=0):
    multiplier = 10 ** decimals
    return math.ceil(n * multiplier) / multiplier

def check_decimals(symbol, client):
    info = client.get_symbol_info(symbol)
    val = info['filters'][2]['stepSize']
    decimal = 0
    is_dec = False
    for c in val:
        if is_dec is True:
            decimal += 1
        if c == '1':
            break
        if c == '.':
            is_dec = True
    return decimal

def fill_pair_decimals(trading_ticker, client):
    dict_decimals = {}
    for ticker in trading_ticker:
        dict_decimals[ticker] = check_decimals(ticker, client)
    return dict_decimals