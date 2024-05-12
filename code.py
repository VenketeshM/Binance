from keys import key, secret
from binance.um_futures import UMFutures
import ta
import ta.momentum
import ta.trend
import pandas as pd
from time import sleep
from binance.error import ClientError

client = UMFutures(key=key, secret=secret)

# 0.012 means +1.2%, 0.009 is -0.9%
tp = 0.003
sl = 0.001
leverage = 10
type = 'ISOLATED'  # type is 'ISOLATED' or 'CROSS'
qty = 100  # Amount of concurrent opened positions


# getting your futures balance in USDT
def get_balance_usdt():
    try:
        response = client.balance(recvWindow=6000)
        for elem in response:
            if elem['asset'] == 'USDT':
                return float(elem['balance'])

    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

# Getting candles for the needed symbol, it's a dataframe with 'Time', 'Open', 'High', 'Low', 'Close', 'Volume'
def klines(symbol):
    try:
        resp = pd.DataFrame(client.klines(symbol, '15m'))
        resp = resp.iloc[:,:6]
        resp.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        resp = resp.set_index('Time')
        resp.index = pd.to_datetime(resp.index, unit = 'ms')
        resp = resp.astype(float)
        return resp
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

# Set leverage for the needed symbol. You need this bcz different symbols can have different leverage
def set_leverage(symbol, level):
    try:
        response = client.change_leverage(
            symbol=symbol, leverage=level, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

# The same for the margin type
def set_mode(symbol, type):
    try:
        response = client.change_margin_type(
            symbol=symbol, marginType=type, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

# Price precision. BTC has 1, XRP has 4
def get_price_precision(symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['pricePrecision']

# Amount precision. BTC has 3, XRP has 1
def get_qty_precision(symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['quantityPrecision']

# Open new order with the last price, and set TP and SL:
def open_order(symbol, side, volume):
    price = float(client.ticker_price(symbol)['price'])
    qty_precision = get_qty_precision(symbol)
    price_precision = get_price_precision(symbol)
    qty = round(volume / price, qty_precision)
    if side == 'buy':
        try:
            resp1 = client.new_order(symbol=symbol, side='BUY', type='LIMIT', quantity=qty, timeInForce='GTC', price=price)
            print(symbol, side, "placing order")
            print(resp1)
            sleep(2)
            sl_price = round(price - price * sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='SELL', type='STOP_MARKET', quantity=qty, timeInForce='GTC', stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price + price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', quantity=qty, timeInForce='GTC', stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
    if side == 'sell':
        try:
            resp1 = client.new_order(symbol=symbol, side='SELL', type='LIMIT', quantity=qty, timeInForce='GTC', price=price)
            print(symbol, side, "placing order")
            print(resp1)
            sleep(2)
            sl_price = round(price + price * sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='BUY', type='STOP_MARKET', quantity=qty, timeInForce='GTC', stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price - price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', quantity=qty, timeInForce='GTC', stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )

# Your current positions (returns the symbols list):
def get_pos():
    try:
        resp = client.get_position_risk()
        pos = []
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                pos.append(elem['symbol'])
        return pos
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

def check_orders():
    try:
        response = client.get_orders(recvWindow=6000)
        sym = []
        for elem in response:
            sym.append(elem['symbol'])
        return sym
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

# Close open orders for the needed symbol. If one stop order is executed and another one is still there
def close_open_orders(symbol):
    try:
        response = client.cancel_open_orders(symbol=symbol, recvWindow=6000)
        print(response)
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

# Strategy. Can use any other:
def str_rsi_signal(symbol):
    kl = klines(symbol)
    rsi = ta.momentum.RSIIndicator(kl.Close).rsi()
    rsi_k = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_k()
    rsi_d = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_d()
    ema = ta.trend.ema_indicator(kl.Close, window=200)
    kl['macd'] = ta.trend.macd_diff(kl.Close)

    if (rsi.iloc[-1] < 40 and ema.iloc[-1] < kl.Close.iloc[-1] and
            rsi_k.iloc[-1] < 20 and rsi_k.iloc[-3] < rsi_d.iloc[-3] and
            rsi_k.iloc[-2] < rsi_d.iloc[-2] and rsi_k.iloc[-1] > rsi_d.iloc[-1] and
            kl['macd'].iloc[-1] > 0):
        return 'up'
    elif (rsi.iloc[-1] > 60 and ema.iloc[-1] > kl.Close.iloc[-1] and
          rsi_k.iloc[-1] > 80 and rsi_k.iloc[-3] > rsi_d.iloc[-3] and
          rsi_k.iloc[-2] > rsi_d.iloc[-2] and rsi_k.iloc[-1] < rsi_d.iloc[-1] and
          kl['macd'].iloc[-1] < 0):
        return 'down'
    elif rsi.iloc[-2] < 30 < rsi.iloc[-1] and kl['macd'].iloc[-1] > 0:
        return 'up'
    elif rsi.iloc[-2] > 70 > rsi.iloc[-1] and kl['macd'].iloc[-1] < 0:
        return 'down'
    else:
        return 'none'


orders = 0
symbol = 'BTCUSDT'

while True:
    # we need to get balance to check if the connection is good, or you have all the needed permissions
    balance = get_balance_usdt()
    sleep(1)
    if balance == None:
        print('Cant connect to API. Check IP, restrictions or wait some time')
    if balance != None:
        print("My balance is: ", balance, " USDT")
        # getting position list:
        pos = []
        pos = get_pos()
        print(f'You have {len(pos)} opened positions:\n{pos}')
        # Getting order list
        ord = []
        ord = check_orders()
        # removing stop orders for closed positions
        for elem in ord:
            if not elem in pos:
                close_open_orders(elem)

        if len(pos) < qty:
            # Calculate the volume to use (half of the balance)
            volume_to_use = balance / 2
            # Strategies (you can make your own with the TA library):
            signal = str_rsi_signal(symbol)

            # 'up' or 'down' signal, we place orders for symbols that arent in the opened positions and orders
            # we also dont need USDTUSDC because its 1:1 (dont need to spend money for the commission)
            if signal == 'up' and not symbol in pos and not symbol in ord:
                print('Found BUY signal for ', symbol)
                set_mode(symbol, type)
                sleep(1)
                set_leverage(symbol, leverage)
                sleep(1)
                print('Placing order for ', symbol)
                open_order(symbol, 'buy', volume_to_use)
                sleep(10)
            if signal == 'down' and not symbol in pos and not symbol in ord:
                print('Found SELL signal for ', symbol)
                set_mode(symbol, type)
                sleep(1)
                set_leverage(symbol, leverage)
                sleep(1)
                print('Placing order for ', symbol)
                open_order(symbol, 'sell', volume_to_use)
                sleep(10)
    print('I am Waiting')
    sleep(60)

