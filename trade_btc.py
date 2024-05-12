from keys import key, secret
from binance.um_futures import UMFutures
import ta
import pandas as pd
from time import sleep
from binance.error import ClientError

client = UMFutures(key=key, secret=secret)

# Constants
tp = 0.010  # Take Profit percentage
sl = 0.005  # Stop Loss percentage
volume = 50  # Volume for one order
leverage = 10  # Leverage
position_limit = 1  # Maximum number of positions to hold at a time
order_wait_time = 60  # Time to wait after placing an order (seconds)
check_interval = 120  # Interval to check for new trade opportunities (seconds)

def get_balance_usdt():
    try:
        response = client.balance(recvWindow=6000)
        for elem in response:
            if elem['asset'] == 'USDC':
                return float(elem['balance'])
    except ClientError as error:
        print_error(error)

def get_tickers_usdt():
    return ['BTCUSDC']  # Only trading BTCUSDC

def klines(symbol):
    try:
        resp = pd.DataFrame(client.klines(symbol, '15m'))
        resp = resp.iloc[:, :6]
        resp.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        resp = resp.set_index('Time')
        resp.index = pd.to_datetime(resp.index, unit='ms')
        resp = resp.astype(float)
        return resp
    except ClientError as error:
        print_error(error)

def set_leverage(symbol, level):
    try:
        response = client.change_leverage(symbol=symbol, leverage=level, recvWindow=6000)
        print(response)
    except ClientError as error:
        print_error(error)

def set_mode(symbol, type):
    try:
        response = client.change_margin_type(symbol=symbol, marginType=type, recvWindow=6000)
        print(response)
    except ClientError as error:
        print_error(error)

def get_price_precision(symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['pricePrecision']

def get_qty_precision(symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['quantityPrecision']

def open_order(symbol, side):
    try:
        price = float(client.ticker_price(symbol)['price'])
        qty_precision = get_qty_precision(symbol)
        price_precision = get_price_precision(symbol)
        qty = round(volume / price, qty_precision)
        if side == 'buy':
            resp1 = client.new_order(symbol=symbol, side='BUY', type='LIMIT', quantity=qty, timeInForce='GTC', price=price)
            print_order_response(resp1)
            sl_price = round(price - price * sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='SELL', type='STOP_MARKET', quantity=qty, timeInForce='GTC', stopPrice=sl_price)
            print_order_response(resp2)
            tp_price = round(price + price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', quantity=qty, timeInForce='GTC', stopPrice=tp_price)
            print_order_response(resp3)
        elif side == 'sell':
            resp1 = client.new_order(symbol=symbol, side='SELL', type='LIMIT', quantity=qty, timeInForce='GTC', price=price)
            print_order_response(resp1)
            sl_price = round(price + price * sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='BUY', type='STOP_MARKET', quantity=qty, timeInForce='GTC', stopPrice=sl_price)
            print_order_response(resp2)
            tp_price = round(price - price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', quantity=qty, timeInForce='GTC', stopPrice=tp_price)
            print_order_response(resp3)
    except ClientError as error:
        print_error(error)

def get_pos():
    try:
        resp = client.get_position_risk()
        pos = []
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                pos.append(elem['symbol'])
        return pos
    except ClientError as error:
        print_error(error)

def check_orders():
    try:
        response = client.get_orders(recvWindow=6000)
        sym = []
        for elem in response:
            sym.append(elem['symbol'])
        return sym
    except ClientError as error:
        print_error(error)

def close_open_orders(symbol):
    try:
        response = client.cancel_open_orders(symbol=symbol, recvWindow=6000)
        print(response)
    except ClientError as error:
        print_error(error)


def str_rsi_signal(symbol):
    # Assuming klines() function fetches historical price data for the symbol
    kl = klines(symbol)
    
    # Calculating RSI and StochRSI
    rsi = ta.momentum.RSIIndicator(kl.Close).rsi()
    rsi_k = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_k()
    rsi_d = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_d()
    
    # Calculating MACD
    kl['macd'] = ta.trend.macd_diff(kl.Close)
    
    # Check MACD and RSI conditions for buy/sell signals
    if kl['macd'].iloc[-1] > 0:
        # Conditions for buy signal
        if ((rsi.iloc[-1] < 40 and 
             rsi_k.iloc[-1] < 20 and 
             rsi_k.iloc[-3] < rsi_d.iloc[-3] and 
             rsi_k.iloc[-2] < rsi_d.iloc[-2] and 
             rsi_k.iloc[-1] > rsi_d.iloc[-1]) or 
            (rsi.iloc[-2] < 30 < rsi.iloc[-1])):
            return 'up'
    elif kl['macd'].iloc[-1] < 0:
        # Conditions for sell signal
        if ((rsi.iloc[-1] > 60 and 
             rsi_k.iloc[-1] > 80 and 
             rsi_k.iloc[-3] > rsi_d.iloc[-3] and 
             rsi_k.iloc[-2] > rsi_d.iloc[-2] and 
             rsi_k.iloc[-1] < rsi_d.iloc[-1]) or 
            (rsi.iloc[-2] > 70 > rsi.iloc[-1])):
            return 'down'
    
    # If none of the conditions are met
    return 'none'


def print_order_response(response):
    print(response)

def print_error(error):
    print(
        "Found error. status: {}, error code: {}, error message: {}".format(
            error.status_code, error.error_code, error.error_message
        )
    )

orders = 0
symbol = ''

while True:
    # we need to get balance to check if the connection is good, or you have all the needed permissions
    balance = get_balance_usdt()
    sleep(1)
    if balance is None:
        print('Can\'t connect to API. Check IP, restrictions or wait some time')
    if balance is not None:
        print("My balance is: ", balance, " USDC")
        # getting position list:
        pos = []
        pos = get_pos()
        print(f'You have {len(pos)} opened positions:\n{pos}')
        # Getting order list
        ord = []
        ord = check_orders()
        # removing stop orders for closed positions
        for elem in ord:
            if elem not in pos:
                close_open_orders(elem)

        if len(pos) < position_limit:
            for elem in get_tickers_usdt():
                signal = str_rsi_signal(elem)  # You can change the signal function here
                if signal == 'up' and elem not in pos and elem not in ord and elem != symbol:
                    print('Found BUY signal for ', elem)
                    set_mode(elem, type)
                    sleep(1)
                    set_leverage(elem, leverage)
                    sleep(1)
                    print('Placing order for ', elem)
                    open_order(elem, 'buy')
                    symbol = elem
                    sleep(order_wait_time)
                    break
                if signal == 'down' and elem not in pos and elem not in ord and elem != symbol:
                    print('Found SELL signal for ', elem)
                    set_mode(elem, type)
                    sleep(1)
                    set_leverage(elem, leverage)
                    sleep(1)
                    print('Placing order for ', elem)
                    open_order(elem, 'sell')
                    symbol = elem
                    sleep(order_wait_time)
                    break

    print('Waiting for next check...')
    sleep(check_interval)
