import csv
import hmac
import json
import hashlib
import requests
import numpy as np
import pandas as pd
from exchange.utils import get_intervals
from datetime import datetime, timezone
from websocket import create_connection, WebSocketConnectionClosedException


class BinanceAPIClient(Exception):
    __intervals = ["1m", "3m", "5m", "15m", "30m",
                   "1h", "2h", "4h", "6h", "8h", "12h",
                   "1d", "3d", "1w", "1M"]  # available intervals for candles
    # headers for candlestick more info in candlesticks_to_pandas method
    __candle_headers = ["t", "o", "h", "l", "c",
                        "v", "T", "q", "n", "V", "Q"]
    __candle_numeric_headers = ["o", "h", "l", "c", "v", "q", "V", "Q"]

    def __init__(self, base_asset=None, quote_asset=None, api_key="", secret_key="", mode="test"):
        """
        :param mode: str: "test" -- start client on binance spot testnet; "prod" -- start client on real binance
        """
        self.base = base_asset
        self.quote = quote_asset
        self.candlestick = []
        self.api = api_key
        self.secret = secret_key
        self.pair = self._get_pair()
        self.ws = None
        self._stream_running = False
        self._stream_id = None
        self._candles_interval = ""
        self._check_pair()
        self._http = None
        self._wss = None
        self.set_mode(mode=mode)

    def __next__(self):
        while self._stream_running:
            # This construction should reconnect to websocket stream if connection was closed by server
            try:
                candle = json.loads(self.ws.recv())
                if candle["k"]["x"]:
                    new_candle = {key: var for key, var in candle["k"].items() if key in self.__candle_headers}
                    candlestick_df = pd.DataFrame(data=new_candle, index=[0])
                    return self._normalize_candlestick_df(candlestick_df)
            except WebSocketConnectionClosedException:
                self._stream_id += 1
                self.start_candle_stream(candles_interval=self._candles_interval, stream_id=self._stream_id)
            if self._stream_running is False:
                raise StopIteration

    def __iter__(self):
        self._stream_running = True
        return self

    def set_settings(self, base_asset, quote_asset, api_key="", secret_key="", mode="test") -> None:
        """Method for changing client settings"""
        self.base = base_asset
        self.quote = quote_asset
        self.api = api_key
        self.secret = secret_key
        self.pair = self._get_pair()
        self._check_pair()
        self.set_mode(mode=mode)

    def set_mode(self, mode="test"):
        if mode == "prod":
            self._http = "https://api.binance.com/"
            self._wss = "wss://stream.binance.com:9443/ws"
        if mode == "test":
            self._http = "https://testnet.binance.vision/"
            self._wss = "wss://testnet.binance.vision/ws"

    def get_wallet_info(self, recv_window=5000) -> pd.DataFrame:
        """
        :return: Pandas dataframe of wallet for gived account
        """
        headers = {"X-MBX-APIKEY": self.api}
        params = {"recvWindow": recv_window, "timestamp": (self.get_now_timestamp())}
        total_params = "&".join([key + "=" + str(value) for key, value in params.items()])
        params["signature"] = self._get_signature(total_params)
        wallet_resp = requests.get(self._http + "api/v3/account",
                                   headers=headers, params=params)
        wallet_data = pd.DataFrame(wallet_resp.json()["balances"]).apply(pd.to_numeric, errors="ignore") \
            .set_index("asset")
        if self.base not in wallet_data.index:
            wallet_data.loc[self.base, :] = [0.0, 0.0]
        return wallet_data

    def new_order(self, side: str, order_type="MARKET", time_in_force="GTC",
                  quantity=None, quote_order_qty=None, price=None,
                  stop_price=None, recv_window=5000):
        """Create new order of 'order_type'

        :param side: str: "BUY" or "SELL"
        :param order_type: str: LIMIT, MARKET, STOP_LOSS, STOP_LOSS_LIMIT, TAKE_PROFIT, TAKE_PROFIT_LIMIT, LIMIT_MAKER
        :param time_in_force: str: 'IOC' -- Immediate Or Cancel, 'GTC' -- Good Til Canceled, 'FOK' -- Fill or Kill
        :param quantity: float or None: MARKET orders using the quantity field specifies
                         the amount of the base asset the user wants to buy or sell at the market price.
                         For example, sending a MARKET order on BTCUSDT will specify how much BTC the user is buying
                         or selling.
        :param price: float
        :param stop_price: float
        :param quote_order_qty: float or None: MARKET orders using quoteOrderQty specifies the amount the user wants
                                to spend (when buying) or receive (when selling) the quote asset; the correct quantity
                                will be determined based on the market liquidity and quoteOrderQty.
                                Using BTCUSDT as an example:
                                On the BUY side, the order will buy as many BTC as quoteOrderQty USDT can.
                                On the SELL side, the order will sell as much BTC needed to receive quoteOrderQty USDT.
        :param recv_window: int: max -- 60_000 With recv_window, you can specify that the request must be processed
                                 within a certain number of milliseconds or be rejected by the server.
        """
        headers = {"X-MBX-APIKEY": self.api}
        params = {"symbol": self.pair, "side": side, "type": order_type}
        if order_type in ["LIMIT", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"]:
            params["timeInForce"] = time_in_force
        if (order_type == "MARKET") and (quantity is None):
            params["quoteOrderQty"] = quote_order_qty
        else:
            params["quantity"] = quantity
        if order_type in ["LIMIT", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT", "LIMIT_MAKER"]:
            params["price"] = price
        if order_type in ["STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"]:
            params["stopPrice"] = stop_price
        params["recvWindow"] = recv_window
        params["timestamp"] = self.get_now_timestamp()
        total_params = "&".join([key + "=" + str(value) for key, value in params.items()])
        params["signature"] = self._get_signature(total_params)
        resp = requests.post(self._http + "api/v3/order", headers=headers, params=params)
        return resp.json()

    def send_test_order(self, side: str, order_type="MARKET", time_in_force="GTC",
                        quantity=None, quote_order_qty=None, price=None,
                        stop_price=None, recv_window=5000):
        """Send test order

        :param side: str: "BUY" or "SELL"
        :param order_type: str: LIMIT, MARKET, STOP_LOSS, STOP_LOSS_LIMIT, TAKE_PROFIT, TAKE_PROFIT_LIMIT, LIMIT_MAKER
        :param time_in_force: str: 'IOC' -- Immediate Or Cancel, 'GTC' -- Good Til Canceled, 'FOK' -- Fill or Kill
        :param quantity: float or None: MARKET orders using the quantity field specifies
                         the amount of the base asset the user wants to buy or sell at the market price.
                         For example, sending a MARKET order on BTCUSDT will specify how much BTC the user is buying
                         or selling.
        :param price: float
        :param stop_price: float
        :param quote_order_qty: float or None: MARKET orders using quoteOrderQty specifies the amount the user wants
                                to spend (when buying) or receive (when selling) the quote asset; the correct quantity
                                will be determined based on the market liquidity and quoteOrderQty.
                                Using BTCUSDT as an example:
                                On the BUY side, the order will buy as many BTC as quoteOrderQty USDT can.
                                On the SELL side, the order will sell as much BTC needed to receive quoteOrderQty USDT.
        :param recv_window: int: max -- 60_000 With recv_window, you can specify that the request must be processed
                                 within a certain number of milliseconds or be rejected by the server.
        """
        headers = {"X-MBX-APIKEY": self.api}
        params = {"symbol": self.pair, "side": side, "type": order_type}
        if order_type in ["LIMIT", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"]:
            params["timeInForce"] = time_in_force
        if (order_type == "MARKET") and (quantity is None):
            params["quoteOrderQty"] = quote_order_qty
        else:
            params["quantity"] = quantity
        if order_type in ["LIMIT", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT", "LIMIT_MAKER"]:
            params["price"] = price
        if order_type in ["STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"]:
            params["stopPrice"] = stop_price
        params["recvWindow"] = recv_window
        params["timestamp"] = self.get_now_timestamp()
        total_params = "&".join([key + "=" + str(value) for key, value in params.items()])
        params["signature"] = self._get_signature(total_params)
        resp = requests.post(self._http + "api/v3/order/test", headers=headers, params=params)
        return resp.json()

    # Get order status with particular id
    def get_order_status(self, order_id, recv_window=5000) -> dict:
        """
        :param order_id: int: Id of order
        :param recv_window: int: max -- 60_000 With recv_window, you can specify that the request must be processed
                                 within a certain number of milliseconds or be rejected by the server.
        :return: information about order with Id 'order_id'
        """
        headers = {"X-MBX-APIKEY": self.api}
        params = {"symbol": self.pair,
                  "orderId": order_id,
                  "recvWindow": recv_window,
                  "timestamp": self.get_now_timestamp()}
        total_params = "&".join([key + "=" + str(value) for key, value in params.items()])
        params["signature"] = self._get_signature(total_params)
        resp = requests.get(self._http + "api/v3/order", headers=headers, params=params)
        return resp.json()

    def get_all_order_status(self, start_time, end_time, recv_window=5000) -> list:
        """Get all account orders from start_time to end_time; active, canceled, or filled.

        :param start_time: timestamp in ms
        :param end_time: timestamp in ms
        :param recv_window: max -- 60_000 With recv_window, you can specify that the request must be processed
                            within a certain number of milliseconds or be rejected by the server.
        :return: list of orders
        """
        headers = {"X-MBX-APIKEY": self.api}
        params = {"symbol": self.pair,
                  "startTime": start_time,
                  "endTime": end_time,
                  "recvWindow": recv_window,
                  "timestamp": self.get_now_timestamp()}
        total_params = "&".join([key + "=" + str(value) for key, value in params.items()])
        params["signature"] = self._get_signature(total_params)
        resp = requests.get(self._http + "api/v3/allOrders", headers=headers, params=params)
        return resp.json()

    # Cancel order with particular id
    def cancel_order(self, order_id, recv_window=5000):
        headers = {"X-MBX-APIKEY": self.api}
        params = {"symbol": self.pair,
                  "orderId": order_id,
                  "recvWindow": recv_window,
                  "timestamp": self.get_now_timestamp()}
        total_params = "&".join([key + "=" + str(value) for key, value in params.items()])
        params["signature"] = self._get_signature(total_params)
        resp = requests.delete(self._http + "api/v3/order", headers=headers, params=params)
        return resp.json()

    # Cancel all orders
    def cancel_all_orders(self, recv_window=5000):
        headers = {"X-MBX-APIKEY": self.api}
        params = {"symbol": self.pair,
                  "recvWindow": recv_window,
                  "timestamp": self.get_now_timestamp()}
        total_params = "&".join([key + "=" + str(value) for key, value in params.items()])
        params["signature"] = self._get_signature(total_params)
        resp = requests.delete(self._http + "api/v3/openOrders", headers=headers, params=params)
        return resp.json()

    # Start websocket candlestik stream
    def start_candle_stream(self, candles_interval: str = "1m", stream_id=1):
        self._stream_id = stream_id
        self._candles_interval = candles_interval
        self.ws = create_connection(self._wss)
        params = {"method": "SUBSCRIBE",
                  "params": ["{symbol}@kline_{interval}".format(symbol=self.pair.lower(), interval=candles_interval)],
                  "id": self._stream_id}
        self.ws.send(json.dumps(params))
        if json.loads(self.ws.recv())["result"] is not None:
            raise Exception("Connection is failed!")
        return self.ws

    # Stop websocket candlestik stream
    def stop_candle_stream(self):
        params = {"method": "UNSUBSCRIBE",
                  "params": ["{symbol}@kline_{interval}".format(symbol=self.pair.lower(),
                                                                interval=self._candles_interval)],
                  "id": self._stream_id}
        self.ws.send(json.dumps(params))
        self._stream_running = False

    def _get_pair(self):
        return self.base + self.quote

    def _check_pair(self):
        data = []
        with open("../exchange/all_pairs.txt", "r") as f:
            for line in f:
                data.append(line.rstrip("\n"))
            if self.pair not in data:
                raise Exception("There is no pair " + self.pair + " in Binance exchange")

    def get_candlestick(self, candles_interval: str = "1m", depth=500) -> None:
        """
        :param candles_interval: m -> minutes; h -> hours; d -> days; w -> weeks; M -> months
            1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        :param depth: max 1000
        """
        self._check_interval(candles_interval)
        params = {"symbol": self.pair, "interval": candles_interval, "limit": depth}
        resp = requests.get(self._http + "api/v3/klines", params=params).json()
        # Here we drop 'Ignore' parameter from candles (last parameter in each list)
        for candle in resp:
            candle.pop()
        self.candlestick = resp

    def get_candlestick_for_given_time(self, start_day: datetime,
                                       end_day: datetime, candles_interval: str = "1m"):
        self._check_interval(candles_interval)
        delta = get_intervals(self.__intervals)[candles_interval]
        start_date = start_day.replace(tzinfo=timezone.utc).timestamp() * 1000
        end_date = end_day.replace(tzinfo=timezone.utc).timestamp() * 1000
        data = []
        while start_date < end_date:
            if start_date + 1000 * delta < end_date:
                params = {"symbol": self.pair, "startTime": int(start_date),
                          "endTime": int(start_date + 1000 * delta), "interval": candles_interval, "limit": 1000}
                start_date += 1000 * delta
                resp = requests.get(self._http + "api/v3/klines", params=params)
                data += resp.json()
            else:
                params = {"symbol": self.pair, "startTime": int(start_date),
                          "endTime": int(end_date), "interval": candles_interval, "limit": 1000}
                start_date += 1000 * delta
                resp = requests.get(self._http + "api/v3/klines", params=params)
                data += resp.json()
        for candle in data:
            candle.pop()
        self.candlestick = data

    def candlesticks_to_pandas(self) -> pd.DataFrame:
        """Names of columns: "t" -- start time; "T" -- close time; "o" -- Open price; "c" -- Close price;
         "h" -- High price; "l" -- Low price; "v" -- Base asset volume; "n" -- Number of trades;
         "q" -- Quote asset volume; "V" -- Taker buy base asset volume; "Q" -- Taker buy quote asset volume

        :return: pd.DataFrame with candles
        """
        data_for_df = self.candlestick
        candlestick_df = pd.DataFrame(np.array(data_for_df), columns=self.__candle_headers)
        return self._normalize_candlestick_df(candlestick_df)

    def save_csv(self):
        data_for_csv = self.candlestick
        with open(self.pair + ".csv", "w", newline="") as f:
            csv_writer = csv.writer(f, delimiter=",")
            csv_writer.writerow(self.__candle_headers)
            csv_writer.writerows(data_for_csv)

    def _get_signature(self, total_params):
        return hmac.new(self.secret.encode(), total_params.encode(), hashlib.sha256).hexdigest()

    def _check_interval(self, interval):
        if interval not in self.__intervals:
            raise Exception("candles_interval must be one of the strings: " + ", ".join(self.__intervals))

    def _normalize_candlestick_df(self, candlestick_df: pd.DataFrame) -> pd.DataFrame:
        """This method rewrite candles from binance to dataframe with to 'standard' form

        :param candlestick_df: dataframe of candles from binance
        :return: dataframe of candles from binance in standard form
        """
        candlestick_df[self.__candle_numeric_headers] = \
            candlestick_df[self.__candle_numeric_headers].apply(pd.to_numeric, errors="ignore")
        candlestick_df["t"] = pd.to_datetime(candlestick_df["t"], utc=True, unit="ms")
        candlestick_df["T"] = pd.to_datetime(candlestick_df["T"], utc=True, unit="ms")
        return candlestick_df.sort_index(axis=1)

    @staticmethod
    def get_server_time():
        resp = requests.get("https://api.binance.com/api/v3/time")
        return resp.json()["serverTime"]

    @staticmethod
    def get_now_timestamp():
        return int(datetime.now().timestamp() * 1000)
