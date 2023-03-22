import os
import ccxt
import datetime
from configparser import ConfigParser
from binance.client import Client
from utils.functions_bollinger import *
from utils.helpers import *
from config import *

# Initialize Variables
CREDENTIALS_PATH = os.path.join(os.path.expanduser('~'), ".binance/credentials")
config = ConfigParser()
config.read(CREDENTIALS_PATH)
api_key = config.get('trade', 'API_KEY')
api_secret  = config.get('trade', 'SECRET_KEY')
binance_client = Client(api_key=api_key, api_secret=api_secret)

# Initialize Variables
holding_quantity = 0
decimals_quantity = check_decimals(symbol=TRADING_TICKER_NAME, client=binance_client)
exchange = ccxt.binance()
currently_holding = False

while 1:
    # STEP 1: FETCH THE CANDLE DATA
    ticker_data = fetch_data(exchange, CCXT_TICKER_NAME, CANDLE_DURATION_IN_MIN)
    
    if ticker_data is not None:
        # STEP 2: COMPUTE THE TECHNICAL INDICATORS & APPLY THE TRADING STRATEGY
        #trade_rec_type = get_trade_recommendation(ticker_data, RSI_OVERSOLD, RSI_OVERBOUGHT)
        trade_rec_type = get_trade_recommendation_MACD(ticker_data)
        print(f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} {CCXT_TICKER_NAME} TRADING RECOMMENDATION: {trade_rec_type}')

        # STEP 3: EXECUTE THE BUY OPERATION
        if (trade_rec_type == 'BUY' and not currently_holding):
            trade_successful, holding_quantity, order_price = execute_trade(binance_client, trade_rec_type, TRADING_TICKER_NAME, INVESTMENT_AMOUNT_DOLLARS, decimals_quantity, holding_quantity)
            currently_holding = not currently_holding if trade_successful else currently_holding
            buy_position = True
            
            # CHECK SELL OPERATION
            while buy_position:
                ticker_data = fetch_data(exchange, CCXT_TICKER_NAME, CANDLE_DURATION_IN_MIN)
                confirm_sell = confirm_sell_operation(ticker_data, 1, exchange, CCXT_TICKER_NAME, order_price)

                if (confirm_sell == "SELL"):
                    trade_successful, holding_quantity, order_price = execute_trade(binance_client, confirm_sell, TRADING_TICKER_NAME, INVESTMENT_AMOUNT_DOLLARS, decimals_quantity, holding_quantity)
                    currently_holding = not currently_holding if trade_successful else currently_holding
                    buy_position = not buy_position
                
                time.sleep(15)

        time.sleep(CANDLE_DURATION_IN_MIN*60)
    else:
        print(f'Unable to fetch ticker data - {CCXT_TICKER_NAME}. Retrying!')

        time.sleep(5)
