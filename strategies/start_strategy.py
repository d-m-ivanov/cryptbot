from exchange.binanceclient import BinanceAPIClient
from strategies.abstract_strategy import AbstractStrategy
from backtester.backtester import BackTester
from datetime import datetime


class StartStrategy:

    def __init__(self, strategy: AbstractStrategy = None, client: BinanceAPIClient = None, mode="BACK_TEST") -> None:
        """
        :param strategy:
        :param client:
        :param mode: "LIVE" -- start strategy on real exchange,
            "TEST" -- start strategy on test spotnet, "BACK_TEST" -- start backtester
        """
        self.mode = mode
        self._strategy = strategy
        self._client = client
        self._back_test = None
        self._start_test = None
        self._end_test = None

    def set_client_settings(self, base_asset, quote_asset, api_key="", secret_key="") -> None:
        self._client.set_settings(base_asset, quote_asset, api_key, secret_key)

    def set_strategy_settings(self, short_term=20, long_term=50, trading_capital=0.2,
                              losses=0.8, candle_interval="5m",) -> None:
        self._strategy.set_settings(short_term=short_term, long_term=long_term,
                                    trading_capital=trading_capital, losses=losses, candle_interval=candle_interval,
                                    client=self._client)

    def set_backtester_settings(self, start_day: datetime, end_day: datetime, base_asset: str, quote_asset: str,
                                base_asset_amount=0.0, quote_asset_amount=100.0):
        self._back_test = BackTester(strategy=self._strategy, base_asset=base_asset, quote_asset=quote_asset,
                                     base_asset_amount=base_asset_amount, quote_asset_amount=quote_asset_amount)
        self._start_test = start_day
        self._end_test = end_day

    def start(self):
        if self.mode == "LIVE":
            self._client.set_mode(mode="prod")
            self.start_strategy()
        if self.mode == "TEST":
            self._client.set_mode(mode="test")
            self.start_strategy()
        if self.mode == "BACK_TEST":
            self.start_back_test()

    def start_strategy(self):
        self._strategy.run_strategy()

    def start_back_test(self):
        self._back_test.run_backtesting(start_day=self._start_test, end_day=self._end_test)

    @property
    def strategy(self) -> AbstractStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: AbstractStrategy) -> None:
        self._strategy = strategy

    @property
    def client(self) -> BinanceAPIClient:
        return self._client

    @client.setter
    def client(self, client: BinanceAPIClient) -> None:
        self._client = client
