from keys import key, secret
from binance.um_futures import UMFutures
import ta
import ta.momentum
import ta.trend
import pandas as pd
from time import sleep
from binance.error import ClientError

client = UMFutures(key=key, secret=secret)

tp = 0.005  # 1 percent
sl = 0.001  # 0.5 percent
volume = 10  # volume for one order (if its 10 and leverage is 10, then you put 1 usdt to one position)
leverage = 10
type = 'ISOLATED'  # type is 'ISOLATED' or 'CROSS'
qty = 1  # Amount of concurrent opened positions

current_trade_open = False
symbol = ''

def get_balance_usdt():
    try:
        response = client.balance(recvWindow=6000)
        for elem in response:
            if elem['asset'] == 'USDT':
                return float(elem['balance'])
    except ClientError as error:
        pass

def get_tickers_usdt():
    tickers = []
    try:
        resp = client.ticker_price()
        for elem in resp:
            if 'USDT' in elem['symbol']:
                tickers.append(elem['symbol'])
        return tickers
    except ClientError as error:
        pass

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
        pass

def set_leverage(symbol, level):
    try:
        client.change_leverage(symbol=symbol, leverage=level, recvWindow=6000)
    except ClientError as error:
        pass

def set_mode(symbol, type):
    try:
        client.change_margin_type(symbol=symbol, marginType=type, recvWindow=6000)
    except ClientError as error:
        pass

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
    price = float(client.ticker_price(symbol)['price'])
    qty_precision = get_qty_precision(symbol)
    price_precision = get_price_precision(symbol)
    qty = round(volume / price, qty_precision)
    if side == 'buy':
        try:
            client.new_order(symbol=symbol, side='BUY', type='LIMIT', quantity=qty, timeInForce='GTC', price=price)
            sleep(2)
            sl_price = round(price - price * sl, price_precision)
            client.new_order(symbol=symbol, side='SELL', type='STOP_MARKET', quantity=qty, timeInForce='GTC', stopPrice=sl_price)
            sleep(2)
            tp_price = round(price + price * tp, price_precision)
            client.new_order(symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', quantity=qty, timeInForce='GTC', stopPrice=tp_price)
        except ClientError as error:
            pass
    if side == 'sell':
        try:
            client.new_order(symbol=symbol, side='SELL', type='LIMIT', quantity=qty, timeInForce='GTC', price=price)
            sleep(2)
            sl_price = round(price + price * sl, price_precision)
            client.new_order(symbol=symbol, side='BUY', type='STOP_MARKET', quantity=qty, timeInForce='GTC', stopPrice=sl_price)
            sleep(2)
            tp_price = round(price - price * tp, price_precision)
            client.new_order(symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', quantity=qty, timeInForce='GTC', stopPrice=tp_price)
        except ClientError as error:
            pass

def get_pos():
    try:
        resp = client.get_position_risk()
        pos = []
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                pos.append(elem['symbol'])
        return pos
    except ClientError as error:
        pass

def check_orders():
    try:
        response = client.get_orders(recvWindow=6000)
        sym = []
        for elem in response:
            sym.append(elem['symbol'])
        return sym
    except ClientError as error:
        pass

def close_open_orders(symbol):
    try:
        client.cancel_open_orders(symbol=symbol, recvWindow=6000)
    except ClientError as error:
        pass

def str_rsi_signal(symbol):
    kl = klines(symbol)
    rsi = ta.momentum.RSIIndicator(kl.Close).rsi()
    rsi_k = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_k()
    rsi_d = ta.momentum.StochRSIIndicator(kl.Close).stochrsi_d()
    kl['macd'] = ta.trend.macd_diff(kl.Close)

    if kl['macd'].iloc[-1] > 0:
        if ((rsi.iloc[-1] < 40 and
            rsi_k.iloc[-1] < 20 and rsi_k.iloc[-3] < rsi_d.iloc[-3] and
            rsi_k.iloc[-2] < rsi_d.iloc[-2] and rsi_k.iloc[-1] > rsi_d.iloc[-1]) or
            (rsi.iloc[-2] < 30 < rsi.iloc[-1])):
            return 'up'
    elif kl['macd'].iloc[-1] < 0:
        if ((rsi.iloc[-1] > 60 and
            rsi_k.iloc[-1] > 80 and rsi_k.iloc[-3] > rsi_d.iloc[-3] and
            rsi_k.iloc[-2] > rsi_d.iloc[-2] and rsi_k.iloc[-1] < rsi_d.iloc[-1]) or
            (rsi.iloc[-2] > 70 > rsi.iloc[-1])):
            return 'down'
    else:
        return 'none'

while True:
    balance = get_balance_usdt()
    sleep(1)
    if balance is not None:
        pos = get_pos()
        ord = check_orders()
        for elem in ord:
            if elem not in pos:
                close_open_orders(elem)

        if not current_trade_open:
            if len(pos) < qty:
                symbols = get_tickers_usdt()
                for elem in symbols:
                    signal = str_rsi_signal(elem)
                    if signal == 'up' and elem != 'USDCUSDT' and elem not in pos and elem not in ord and elem != symbol:
                        set_mode(elem, type)
                        sleep(1)
                        set_leverage(elem, leverage)
                        sleep(1)
                        open_order(elem, 'buy')
                        symbol = elem
                        current_trade_open = True
                        pos = get_pos()
                        sleep(1)
                        ord = check_orders()
                        sleep(1)
                        sleep(10)
                        break
                    elif signal == 'down' and elem != 'USDCUSDT' and elem not in pos and elem not in ord and elem != symbol:
                        set_mode(elem, type)
                        sleep(1)
                        set_leverage(elem, leverage)
                        sleep(1)
                        open_order(elem, 'sell')
                        symbol = elem
                        current_trade_open = True
                        pos = get_pos()
                        sleep(1)
                        ord = check_orders()
                        sleep(1)
                        sleep(10)
                        break
    sleep(60)
