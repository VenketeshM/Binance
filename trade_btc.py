from keys import key, secret
from binance.um_futures import UMFutures
import ta
import ta.momentum
import ta.trend
import pandas as pd
from time import sleep
from binance.error import ClientError

client = UMFutures(key=key, secret=secret)

# This is btc trade 
tp = 0.005  # 1 percent
sl = 0.001  # 0.5 percent
volume = 50  # volume for one order (if its 10 and leverage is 10, then you put 1 usdt to one position)
leverage = 10
type = 'ISOLATED'  # type is 'ISOLATED' or 'CROSS'
qty = 1  # Amount of concurrent opened positions

current_trade_open = False
symbol = ''

# getting your futures balance in USDT
def get_balance_usdt():
    try:
        response = client.balance(recvWindow=6000)
        for elem in response:
            if elem['asset'] == 'USDT':
                return float(elem['balance'])
    except ClientError as error:
        print("Error occurred:", error)

# Getting candles for the needed symbol
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
        print("Error occurred:", error)

# Set leverage for the needed symbol
def set_leverage(symbol, level):
    try:
        response = client.change_leverage(
            symbol=symbol, leverage=level, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print("Error occurred:", error)

# The same for the margin type
def set_mode(symbol, type):
    try:
        response = client.change_margin_type(
            symbol=symbol, marginType=type, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print("Error occurred:", error)

# Open new order with the last price, and set TP and SL
def open_order(symbol, side):
    price = float(client.ticker_price(symbol)['price'])
    qty_precision = 3  # BTCUSDC has 3 qty precision
    price_precision = 2  # BTCUSDC has 2 price precision
    qty = round(volume / price, qty_precision)
    if side == 'buy':
        try:
            resp1 = client.new_order(symbol=symbol, side='BUY', type='LIMIT', quantity=qty, timeInForce='GTC',
                                     price=price)
            print(symbol, side, "placing order")
            print(resp1)
            sleep(2)
            sl_price = round(price - price * sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='SELL', type='STOP_MARKET', quantity=qty, timeInForce='GTC',
                                     stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price + price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', quantity=qty,
                                     timeInForce='GTC', stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print("Error occurred:", error)
    if side == 'sell':
        try:
            resp1 = client.new_order(symbol=symbol, side='SELL', type='LIMIT', quantity=qty, timeInForce='GTC',
                                     price=price)
            print(symbol, side, "placing order")
            print(resp1)
            sleep(2)
            sl_price = round(price + price * sl, price_precision)
            resp2 = client.new_order(symbol=symbol, side='BUY', type='STOP_MARKET', quantity=qty, timeInForce='GTC',
                                     stopPrice=sl_price)
            print(resp2)
            sleep(2)
            tp_price = round(price - price * tp, price_precision)
            resp3 = client.new_order(symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', quantity=qty,
                                     timeInForce='GTC', stopPrice=tp_price)
            print(resp3)
        except ClientError as error:
            print("Error occurred:", error)

# Your current positions (returns the symbols list)
def get_pos():
    try:
        resp = client.get_position_risk()
        pos = []
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                pos.append(elem['symbol'])
        return pos
    except ClientError as error:
        print("Error occurred:", error)

def check_orders():
    try:
        response = client.get_orders(recvWindow=6000)
        sym = []
        for elem in response:
            sym.append(elem['symbol'])
        return sym
    except ClientError as error:
        print("Error occurred:", error)

def close_open_orders(symbol):
    try:
        response = client.cancel_open_orders(symbol=symbol, recvWindow=6000)
        print(response)
    except ClientError as error:
        print("Error occurred:", error)

def str_rsi_signal(symbol):
    kl = klines(symbol)
    rsi = ta.momentum.RSIIndicator(kl.Close).rsi()
    rsi_k = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_k()
    rsi_d = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_d()
    kl['macd'] = ta.trend.macd_diff(kl.Close)

    if (rsi.iloc[-1] < 40 and
            rsi_k.iloc[-1] < 20 and rsi_k.iloc[-3] < rsi_d.iloc[-3] and
            rsi_k.iloc[-2] < rsi_d.iloc[-2] and rsi_k.iloc[-1] > rsi_d.iloc[-1] and
            kl['macd'].iloc[-1] > 0):
        return 'up'
    elif (rsi.iloc[-1] > 60 and
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

while True:
    balance = get_balance_usdt()
    sleep(1)
    if balance is None:
        print('Cannot connect to API. Check IP, restrictions, or wait some time')
    if balance is not None:
        print("My balance is: ", balance, " USDT")
        pos = get_pos()
        print(f'You have {len(pos)} opened positions:\n{pos}')
        ord = check_orders()
        for elem in ord:
            if elem not in pos:
                close_open_orders(elem)

        if not current_trade_open:
            if len(pos) < qty:
                symbol = 'BTCUSDC'
                signal = str_rsi_signal(symbol)
                if signal == 'up' and symbol not in pos and symbol not in ord:
                    print('Found BUY signal for ', symbol)
                    set_mode(symbol, type)
                    sleep(1)
                    set_leverage(symbol, leverage)
                    sleep(1)
                    print('Placing order for ', symbol)
                    open_order(symbol, 'buy')
                    current_trade_open = True
                elif signal == 'down' and symbol not in pos and symbol not in ord:
                    print('Found SELL signal for ', symbol)
                    set_mode(symbol, type)
                    sleep(1)
                    set_leverage(symbol, leverage)
                    sleep(1)
                    print('Placing order for ', symbol)
                    open_order(symbol, 'sell')
                    current_trade_open = True
    print('Waiting 1 minute')
    sleep(60)
