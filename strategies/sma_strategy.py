import pandas as pd
import numpy as np
from exchange.binanceclient import BinanceAPIClient
from strategies.abstract_strategy import AbstractStrategy


class SMAStrategy(AbstractStrategy):

    def __init__(self, short_term=20, long_term=50, trading_capital=0.2,
                 client: BinanceAPIClient = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.short_term = short_term  # This is amount of variables for short term simple moving averages
        self.long_term = long_term  # This is amount of variables for long term simple moving averages
        self._client = client
        self._trading_capital = trading_capital
        self._position_open = False
        self._running = False
        self._buy_order_id = None
        self._sell_order_id = None

    def set_settings(self, short_term=20, long_term=50,
                     client: BinanceAPIClient = None):
        self.short_term = short_term
        self.long_term = long_term
        self._client = client

    def run(self, interval="5m", stream_id=1):
        self._running = True
        # Load history
        price_data = self.get_history(interval=interval)
        # Start websocket stream of candles
        self._client.start_candle_stream(candles_interval=interval, stream_id=stream_id)
        i = self.long_term
        for candle in self._client:
            # Check orders
            self.check_buy_order()
            self.check_sell_order()
            # Update wallet data
            wallet_data = self._client.get_wallet_info()
            # Update
            price_data.loc[i, ["close_time", "close_price"]] = [pd.to_datetime(candle["T"], utc=True, unit="ms"),
                                                                float(candle["c"])]
            # Add new simple moving averages
            price_data.loc[i, str(self.short_term) + "_SMA"] = price_data.tail(self.short_term)["close_price"].mean()
            price_data.loc[i, str(self.long_term) + "_SMA"] = price_data.tail(self.long_term)["close_price"].mean()
            # Check if we want to buy
            if self.signal_buy(price_data=price_data, step=i):
                trading_capital = wallet_data[self._client.quote_asset] * self._trading_capital
                response = self._client.new_order(side="BUY", quote_order_qty=trading_capital)
                # Here we memorize id of buy order
                self._buy_order_id = response["orderId"]
            # Check if we want to sell
            if self.signal_sell(price_data=price_data, step=i):
                amount_of_sell = wallet_data[self._client.base_asset]
                response = self._client.new_order(side="SELL", quantity=amount_of_sell)
                # Here we memorize id of sell order
                self._sell_order_id = response["orderId"]
            # Update data and counter
            i += 1

    def get_history(self, interval: str) -> pd.DataFrame:
        # Use client for getting history data
        self._client.get_candlestick(candles_interval=interval, depth=self.long_term + 1)
        price_hist = self._client.candlesticks_to_pandas()
        price_data = pd.DataFrame(columns=["close_time",
                                           "close_price"])
        price_data[["close_time", "close_price"]] = price_hist[['close_time', 'close']]
        # Drop last candle because this is not closed
        price_data = price_data.drop(index=self.long_term, axis=0)
        # Calculate simple moving averages for short and long terms
        price_data[str(self.short_term) + "_SMA"] = price_data["close_price"] \
            .rolling(window=self.short_term).mean()
        price_data[str(self.long_term) + "_SMA"] = price_data["close_price"] \
            .rolling(window=self.long_term).mean()
        return price_data

    def signal_buy(self, price_data: pd.DataFrame, step: int) -> bool:
        # Check moving averages on this step
        if price_data.loc[step, str(self.short_term) + "_SMA"] > price_data.loc[step, str(self.long_term) + "_SMA"]:
            # Check moving averages on previous step and status of a position
            signal = ((price_data.loc[step - 1, str(self.short_term) + "_SMA"] <
                       price_data.loc[step - 1, str(self.long_term) + "_SMA"]) and (self._position_open is False))
        else:
            signal = False
        return signal

    def signal_sell(self, price_data: pd.DataFrame, step: int) -> bool:
        # Check moving averages on this step
        if price_data.loc[step, str(self.short_term) + "_SMA"] < price_data.loc[step, str(self.long_term) + "_SMA"]:
            # Check moving averages on previous step and status of a position
            signal = ((price_data.loc[step - 1, str(self.short_term) + "_SMA"] >
                       price_data.loc[step - 1, str(self.long_term) + "_SMA"]) and self._position_open)
        else:
            signal = False
        return signal

    def check_buy_order(self) -> None:
        """
        Check if buy order filled.
        If order is filled set position_open = True, and forget buy_order_id.
        """
        if self._buy_order_id is not None:
            order_status = self._client.get_order_status(order_id=self._buy_order_id)["status"]
            if order_status == "FILLED":
                self._position_open = True
                self._buy_order_id = None

    def check_sell_order(self):
        """
        Check if sell order filled.
        If order is filled set position_open = False, and forget sell_order_id.
        """
        if self._sell_order_id is not None:
            order_status = self._client.get_order_status(order_id=self._sell_order_id)["status"]
            if order_status == "FILLED":
                self._position_open = False
                self._sell_order_id = None

    def stop(self):
        self._running = False
