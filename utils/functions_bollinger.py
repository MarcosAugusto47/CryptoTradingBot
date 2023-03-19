import numpy as np
import pandas as pd
import talib
import time
from datetime import datetime
from binance.enums import *

from utils.helpers import check_decimals, round_up, round_down

def fetch_data(exchange_client, ticker, candle_duration_in_min):
    bars, ticker_df = None, None

    try:
        bars = exchange_client.fetch_ohlcv(ticker, timeframe=f'{candle_duration_in_min}m', limit=100)
    except:
        print(f"Error in fetching data from the exchange:{ticker}")

    if bars is not None:
        # tranforming the data to a pandas Dataframe and deleting last row, because it refers to a non-closed candle
        ticker_df = pd.DataFrame(bars[:-1], columns=['at', 'open', 'high', 'low', 'close', 'vol'])
        # creating new column of Date based on the time in ms column
        ticker_df['Date'] = pd.to_datetime(ticker_df['at'], unit='ms')
        # creating column of the symbol
        ticker_df['symbol'] = ticker

    return ticker_df

def get_current_price(exchange_client, ticker, candle_duration_in_min):
    bars, ticker_df = None, None

    try:
        bars = exchange_client.fetch_ohlcv(ticker, timeframe=f'{candle_duration_in_min}m', limit=100)
    except:
        print(f"Error in getting current price for {ticker}")

    if bars is not None:
        # tranforming the data to a pandas Dataframe and deleting last row, because it refers to a non-closed candle
        ticker_df = pd.DataFrame(bars[-1:], columns=['at', 'open', 'high', 'low', 'close', 'vol'])
        current_price = ticker_df['close'][0]

    return current_price

def get_trade_recommendation_MACD(ticker_df):
    macd_result = 'WAIT'

    # BUY or SELL based on MACD crossover points and the RSI value at that point
    macd, signal, hist = talib.MACD(ticker_df['close'], fastperiod = 12, slowperiod = 26, signalperiod = 9)
    last_hist = hist.iloc[-1]
    prev_hist = hist.iloc[-2]

    if not np.isnan(prev_hist) and not np.isnan(last_hist):
        # If hist value has changed from negative to positive or vice versa, it indicates a crossover
        macd_crossover = (abs(last_hist + prev_hist)) != (abs(last_hist) + abs(prev_hist))
        if macd_crossover:
            macd_result = 'BUY' if last_hist > 0 else 'SELL'

    return macd_result

def get_trade_recommendation(ticker_df, rsi_oversold, rsi_overbought):

    macd_result = 'WAIT'
    rsi_result = 'WAIT'

    # BUY or SELL based on MACD crossover points and the RSI value at that point
    macd, signal, hist = talib.MACD(ticker_df['close'], fastperiod = 12, slowperiod = 26, signalperiod = 9)
    last_hist = hist.iloc[-1]
    prev_hist = hist.iloc[-2]
    
    if not np.isnan(prev_hist) and not np.isnan(last_hist):
        # If hist value has changed from negative to positive or vice versa, it indicates a crossover
        macd_crossover = (abs(last_hist + prev_hist)) != (abs(last_hist) + abs(prev_hist))
        if macd_crossover:
            macd_result = 'BUY' if last_hist > 0 else 'SELL'

    if macd_result != 'WAIT':
        rsi = talib.RSI(ticker_df['close'], timeperiod = 14)
        # Consider last 3 RSI values
        last_rsi_values = rsi.iloc[-3:]

        if (last_rsi_values.min() <= rsi_oversold):
            rsi_result = 'BUY'
        elif (last_rsi_values.max() >= rsi_overbought):
            rsi_result = 'SELL'

    #print("MACD Result:", macd_result, "Final Result:", rsi_result)
    return rsi_result if rsi_result == macd_result else 'WAIT'

def confirm_sell_operation(ticker_df, weight, exchange, ccxt_ticker_name, order_price):
    bollinger_result = 'WAIT'
    
    # 20-window moving average 
    ticker_df['sma_bb'] = ticker_df['close'].rolling(window=20).mean()
    # upper and lower bollinger bands: SMA +/- 2 * standard deviation
    ticker_df['stddev'] = ticker_df['close'].rolling(window=20).std()
    ticker_df['upper_boll1'] = ticker_df['sma_bb'] + (1 * ticker_df['stddev'])
    ticker_df['weighted_upper_boll1'] = ticker_df['sma_bb'] + (1 * weight * ticker_df['stddev'])
    # ticker_df['upper_boll2'] = ticker_df['sma_bb'] + (2 * ticker_df['stddev'])
    # ticker_df['lower_boll1'] = ticker_df['sma_bb'] - (1 * ticker_df['stddev'])
    # ticker_df['lower_boll2'] = ticker_df['sma_bb'] - (2 * ticker_df['stddev'])
    upper_boll1_price = ticker_df['upper_boll1'].iloc[-1]
    weighted_upper_boll1_price = ticker_df['weighted_upper_boll1'].iloc[-1]
    # upper_boll2_price = ticker_df['upper_boll2'].iloc[-1]
    # lower_boll1_price = ticker_df['lower_boll1'].iloc[-1]
    # lower_boll2_price = ticker_df['lower_boll2'].iloc[-1]

    last_price = exchange.fetch_ticker(ccxt_ticker_name)['last']

    if not np.isnan(last_price):
        sigma_reached = last_price >= weighted_upper_boll1_price
        if sigma_reached:
            bollinger_result = 'SELL'

    if not np.isnan(last_price):
        price_loss_limit = 0.996*order_price
        lost_reached = last_price <= price_loss_limit
        if lost_reached:
            bollinger_result = 'SELL'
    
    print(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}: "
          f"Last price: {last_price}; Weighted Bollinger 1 Sigma:{weighted_upper_boll1_price}; Price Loss Limit: {price_loss_limit}")
    
    return bollinger_result

def wait_operation_filling(binance_client, order):
    not_filled=True
    while not_filled:
        print("Waiting operation filling...")
        order_status = binance_client.get_order(symbol=order['symbol'], orderId=str(order['orderId']))['status']
        if (order_status == 'FILLED'):
            not_filled = not not_filled
        time.sleep(10)

    #print("Order filled!")

# def execute_trade(binance_client, trade_rec_type, trading_ticker, investiment_amount_dollars, decimals_quantity, holding_quantity):
#     order_placed = False
#     side_value = SIDE_BUY if (trade_rec_type == "BUY") else SIDE_SELL
#     try:
#         df = pd.DataFrame(binance_client.get_all_tickers())
#         df = df[df.symbol == trading_ticker]
#         if True:
#             current_price = float(df['price'])
#             script_quantity = round_up(investiment_amount_dollars/current_price, decimals_quantity) if trade_rec_type == "BUY" else holding_quantity
#             print(f"PLACING ORDER {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}: "
#                   f"{trading_ticker}, {side_value}, {current_price}, {script_quantity}, {int(time.time() * 1000)} ")
            
#             order_response = binance_client.create_order(symbol=trading_ticker,
#                                                          side = side_value,
#                                                          type=ORDER_TYPE_LIMIT,
#                                                          timeInForce = TIME_IN_FORCE_GTC,
#                                                          quantity=script_quantity,
#                                                          price=str(current_price))
                        
#             print(f"ORDER PLACED")
#             wait_operation_filling(binance_client, order_response)
#             print(f"ORDER EXECUTED!")
#             holding_quantity = script_quantity if trade_rec_type == "BUY" else holding_quantity
#             order_placed = True

#     except:
#         print(f"\nALERT!!! UNABLE TO COMPLETE ORDER")
    
#     return order_placed, holding_quantity, current_price

def execute_trade(binance_client, trade_rec_type, trading_ticker, investiment_amount_dollars, decimals_quantity, holding_quantity):
    order_placed = False
    side_value = SIDE_BUY if (trade_rec_type == "BUY") else SIDE_SELL
    
    df = pd.DataFrame(binance_client.get_all_tickers())
    df = df[df.symbol == trading_ticker]
    if True:
        current_price = float(df['price'])
        script_quantity = round_down(investiment_amount_dollars/current_price, decimals_quantity) if trade_rec_type == "BUY" else holding_quantity
        print(f"PLACING ORDER {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}: "
                f"{trading_ticker}, {side_value}, {current_price}, {script_quantity}, {int(time.time() * 1000)} ")
        
        order_response = binance_client.create_order(symbol=trading_ticker,
                                                     side = side_value,
                                                     type=ORDER_TYPE_LIMIT,
                                                     timeInForce = TIME_IN_FORCE_GTC,
                                                     quantity=script_quantity,
                                                     price=str(current_price))
                    
        print(f"ORDER PLACED")
        wait_operation_filling(binance_client, order_response)
        print(f"ORDER EXECUTED!")
        # put zero in the end for sell operation?
        holding_quantity = script_quantity if trade_rec_type == "BUY" else holding_quantity
        order_placed = True
   
    return order_placed, holding_quantity, current_price