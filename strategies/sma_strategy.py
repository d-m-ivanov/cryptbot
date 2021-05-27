import pandas as pd
import numpy as np
from exchange.binanceclient import BinanceAPIClient
from strategies.abstract_strategy import AbstractStrategy


class SMAStrategy(AbstractStrategy):

    def __init__(self, short_term=20, long_term=50,
                 client: BinanceAPIClient = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.short_term = short_term # This is amount of variables for short term simple moving averages
        self.long_term = long_term # This is amount of variables for long term simple moving averages
        self._client = client
        self._position_open = False
        self._running = False

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
            # Update data (add new candle)
            price_data.loc[i, ["close_time", "close_price"]] = [pd.to_datetime(candle["T"], utc=True, unit="ms"),
                                                                float(candle["c"])]
            # Add new simple moving averages
            price_data.loc[i, str(self.short_term) + "_SMA"] = price_data.tail(self.short_term)["close_price"].mean()
            price_data.loc[i, str(self.long_term) + "_SMA"] = price_data.tail(self.long_term)["close_price"].mean()
            # Check if we want to buy
            if self.test_buy(price_data=price_data, step=i):
                self._position_open = True
                self._client.new_order(side="BUY", quote_order_qty=0)
            # Check if we want to sell
            if self.test_sell(price_data=price_data, step=i):
                self._position_open = False
                self._client.new_order(side="SELL", quantity=0)
            # Update counter
            i += 1

    def get_history(self, interval: str) -> pd.DataFrame:
        # Use client for getting history data
        self._client.get_candlestick(candles_interval=interval, depth=self.long_term + 1)
        price_hist = self._client.candlesticks_to_pandas()
        price_data = pd.DataFrame(columns=["close_time",
                                           "close_price"])
        price_data[["close_time", "close_price"]] = price_hist[['close_time', 'close']]
        # Drop last candle
        price_data = price_data.drop(index=self.long_term, axis=0)
        # Calculate simple moving averages for short ans long terms
        price_data[str(self.short_term) + "_SMA"] = price_data["close_price"] \
            .rolling(window=self.short_term).mean()
        price_data[str(self.long_term) + "_SMA"] = price_data["close_price"] \
            .rolling(window=self.long_term).mean()
        return price_data

    def test_buy(self, price_data: pd.DataFrame, step: int) -> bool:
        # Check moving averages on this step
        if price_data.loc[step, str(self.short_term) + "_SMA"] > price_data.loc[step, str(self.long_term) + "_SMA"]:
            # Check moving averages on this on previous step and status of a position
            signal = ((price_data.loc[step - 1, str(self.short_term) + "_SMA"] <
                       price_data.loc[step - 1, str(self.long_term) + "_SMA"]) and (self._position_open is False))
        else:
            signal = False
        return signal

    def test_sell(self, price_data: pd.DataFrame, step: int) -> bool:
        if price_data.loc[step, str(self.short_term) + "_SMA"] < price_data.loc[step, str(self.long_term) + "_SMA"]:
            signal = ((price_data.loc[step - 1, str(self.short_term) + "_SMA"] >
                       price_data.loc[step - 1, str(self.long_term) + "_SMA"]) and (self._position_open is True))
        else:
            signal = False
        return signal

    def stop(self):
        self._running = False
