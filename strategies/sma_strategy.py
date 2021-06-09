import pandas as pd
from exchange.binanceclient import BinanceAPIClient
from strategies.abstract_strategy import AbstractStrategy


class SMAStrategy(AbstractStrategy):

    def __init__(self, short_term=20, long_term=50, trading_capital=0.2,
                 losses=0.8, candle_interval="5m", client: BinanceAPIClient = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.short_term = short_term  # This is amount of variables for short term simple moving averages
        self.long_term = long_term  # This is amount of variables for long term simple moving averages
        self._client = client
        self.trading_capital = trading_capital
        self.interval = candle_interval
        self._losses = losses
        self.position_open = False
        self._buy_order_id = None
        self._sell_order_id = None

    def __str__(self):
        return f"SMAStrategy_{self.interval}_{self.short_term}_SMA_{self.long_term}_SMA_"

    def set_settings(self, short_term=20, long_term=50,
                     trading_capital=0.2, losses=0.8, candle_interval="5m", client: BinanceAPIClient = None):
        self.short_term = short_term
        self.long_term = long_term
        self._client = client
        self.trading_capital = trading_capital
        self.interval = candle_interval
        self._losses = losses

    def run_strategy(self, stream_id=1, recv_window=5000):
        # Load wallet data
        wallet_data = self._client.get_wallet_info(recv_window=recv_window)
        # Write capital we have
        capital = wallet_data.loc[self._client.quote, "free"]
        # Load history
        price_data = self.get_history(interval=self.interval)
        # Start websocket stream of candles
        self._client.start_candle_stream(candles_interval=self.interval, stream_id=stream_id)
        i = self.long_term
        for candle in self._client:
            # Check orders
            self.check_buy_order(recv_window=recv_window)
            self.check_sell_order(recv_window=recv_window)
            # Update
            price_data.loc[i, ["close_time", "close_price"]] = self.candle_preprocessing(candle) \
                .loc[0, ["close_time", "close_price"]]
            # Compute new simple moving averages
            price_data = self.compute(price_data, step=i)
            # Update wallet data
            wallet_data = self._client.get_wallet_info(recv_window=recv_window)
            total_assets = (wallet_data.loc[self._client.quote, "free"]
                            + wallet_data.loc[self._client.base, "free"] * price_data.loc[i, "close_price"])
            # if we lost 20% of capital -- stop strategy
            self.stop_strategy(total_assets=total_assets, capital=capital,
                               wallet_data=wallet_data, recv_window=recv_window)
            # Send sell or buy orders if we want to
            self.send_order(price_data=price_data, wallet_data=wallet_data, step=i, recv_window=recv_window)
            # Update counter
            i += 1

    def get_history(self, interval: str) -> pd.DataFrame:
        # Use client for getting history data
        self._client.get_candlestick(candles_interval=interval, depth=self.long_term + 1)
        price_hist = self._client.candlesticks_to_pandas()
        price_data = SMAStrategy.candle_preprocessing(price_hist)
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
                       price_data.loc[step - 1, str(self.long_term) + "_SMA"]) and (self.position_open is False))
        else:
            signal = False
        return signal

    def signal_sell(self, price_data: pd.DataFrame, step: int) -> bool:
        # Check moving averages on this step
        if price_data.loc[step, str(self.short_term) + "_SMA"] < price_data.loc[step, str(self.long_term) + "_SMA"]:
            # Check moving averages on previous step and status of a position
            signal = ((price_data.loc[step - 1, str(self.short_term) + "_SMA"] >
                       price_data.loc[step - 1, str(self.long_term) + "_SMA"]) and self.position_open)
        else:
            signal = False
        return signal

    def send_order(self, price_data, wallet_data, step, recv_window) -> None:
        """This method sends buy or sell orders

        :param price_data: price data on this step
        :param wallet_data: wallet data on this step
        :param step: number of steps in ren_strategy method
        :param recv_window: parameter of orders
        """
        # Check if we want to buy
        if self.signal_buy(price_data=price_data, step=step):
            trading_capital = wallet_data.loc[self._client.quote, "free"] * self.trading_capital
            response = self._client.new_order(side="BUY", quote_order_qty=trading_capital, recv_window=recv_window)
            # Here we memorize id of buy order
            self._buy_order_id = response["orderId"]
        # Check if we want to sell
        if self.signal_sell(price_data=price_data, step=step):
            amount_of_sell = wallet_data.loc[self._client.base, "free"]
            response = self._client.new_order(side="SELL", quantity=amount_of_sell, recv_window=recv_window)
            # Here we memorize id of sell order
            self._sell_order_id = response["orderId"]

    def compute(self, price_data: pd.DataFrame, step) -> pd.DataFrame:
        price_data.loc[step, str(self.short_term) + "_SMA"] = price_data.tail(self.short_term)["close_price"].mean()
        price_data.loc[step, str(self.long_term) + "_SMA"] = price_data.tail(self.long_term)["close_price"].mean()
        return price_data

    def check_buy_order(self, recv_window) -> None:
        """Check if buy order filled.
        If order is filled set position_open = True, and forget buy_order_id.
        """
        if self._buy_order_id is not None:
            order_status = self._client.get_order_status(order_id=self._buy_order_id, recv_window=recv_window)
            if order_status["status"] == "FILLED":
                self.position_open = True
                self._buy_order_id = None
            elif order_status["status"] == "EXPIRED":
                self.position_open = True
                self._buy_order_id = None

    def check_sell_order(self, recv_window):
        """Check if sell order filled.
        If order is filled set position_open = False, and forget sell_order_id.
        """
        if self._sell_order_id is not None:
            order_status = self._client.get_order_status(order_id=self._sell_order_id, recv_window=recv_window)
            if order_status["status"] == "FILLED":
                self.position_open = False
                self._sell_order_id = None
            elif order_status["status"] == "EXPIRED":
                self.position_open = False
                self._sell_order_id = None

    def stop_strategy(self, total_assets, capital, wallet_data, recv_window) -> None:
        """ This method decides stop trading or not

        :param total_assets: All quote asset we have (including quote asset in form base asset)
        :param capital: Quote asset in the beginning of trading
        :param recv_window: parameter of orders
        """
        if total_assets < capital * self._losses:
            self._client.cancel_order(order_id=self._buy_order_id, recv_window=recv_window)
            if self.position_open:
                amount_of_sell = wallet_data.loc[self._client.base, "free"]
                self._client.new_order(side="SELL", quantity=amount_of_sell, recv_window=recv_window)
            self._client.stop_candle_stream()

    @staticmethod
    def candle_preprocessing(candles_data: pd.DataFrame) -> pd.DataFrame:
        return candles_data[["T", "c"]].rename(columns={"T": "close_time", "c": "close_price"})
