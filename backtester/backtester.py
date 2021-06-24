import os
import pandas as pd
from exchange.binanceclient import BinanceAPIClient
from strategies.abstract_strategy import AbstractStrategy
from strategies.sma_strategy import SMAStrategy
from datetime import datetime


class BackTester:

    def __init__(self, strategy: [AbstractStrategy, SMAStrategy], base_asset=None, quote_asset=None,
                 base_asset_amount=0.0, quote_asset_amount=100.0):
        """
        :param strategy: This is a strategy we wanna to test
        :param base_asset: This is a base asset of test
        :param quote_asset: This is a base quote of test
        :param base_asset_amount: This is amount of base asset we have in the start of testing
        :param quote_asset_amount: This is amount of quote asset we have in the start of testing
        """
        self.base = base_asset
        self.quote = quote_asset
        self.assets = [self.base, self.quote]
        self.base_amount = base_asset_amount
        self.quote_amount = quote_asset_amount
        self.assets_amount = [self.base_amount, self.quote_amount]
        self._strategy = strategy

    def run_backtesting(self, start_day: datetime, end_day: datetime) -> None:
        """This is a core method of backtester. Here we grab a strategy and analyse data with it

        :param start_day: datetime from which we start our backtest
        :param end_day: datetime in which we stop our backtest
        :return: In the end of iteration this method makes report in form of excel file
        """
        file_name = (str(self._strategy) + self.base + self.quote + "_")  # Create name of a file for report
        hist_data = self.get_historical_candles(start_day=start_day, end_day=end_day)  # Get historical data
        hist_data[self.assets] = self.assets_amount  # Add info of our capital
        # Prepare data for iteration
        price_data = hist_data.loc[: self._strategy.long_term-1, :]
        number_of_candles = hist_data.shape[0]
        for i in range(self._strategy.long_term, number_of_candles):
            # Add new data to price data
            price_data = pd.concat([price_data, hist_data.iloc[i: i+1]])
            # Compute data with strategy
            price_data = self._strategy.compute(price_data=price_data, step=i)
            # Decide if we wanna buy/sell or do nothing
            self.mock_order(price_data=price_data, step=i)
        # Create report
        self.form_report(price_data=price_data, file_name=file_name)

    def get_historical_candles(self, start_day: datetime, end_day: datetime) -> pd.DataFrame:
        """This is a support method which extracts historical data from exchange

        :param start_day: datetime from which we start our backtest
        :param end_day: datetime in which we stop our backtest
        :return: pd.DataFrame with historical candles
        """
        client = BinanceAPIClient(base_asset=self.base, quote_asset=self.quote, mode="prod")
        client.get_candlestick_for_given_time(start_day, end_day, self._strategy.interval)
        candles_data = client.candlesticks_to_pandas()
        return self._strategy.candle_preprocessing(candles_data)

    def mock_order(self, price_data: pd.DataFrame, step: int) -> None:
        """This method checks if we wanna buy or sell on base of a strategy.
        If so method adds info about trade into dataframe

        :param price_data: dataframe with data on current step of iteration
        :param step: step of iteration
        """
        # Check if we want to buy
        if self._strategy.signal_buy(price_data=price_data, step=step):
            # Add base asset on the current price
            self.base_amount += (self.quote_amount * self._strategy.trading_capital
                                 / price_data.loc[step, "close_price"])
            # Calculate how much of quote asset we must pay
            self.quote_amount -= self.quote_amount * self._strategy.trading_capital
            # Update amount of assets we have
            self.assets_amount = [self.base_amount, self.quote_amount]
            # Write info about our assets in to dataframe
            price_data.loc[step, self.assets] = self.assets_amount
            self._strategy.position_open = True
        # Check if we want to sell
        elif self._strategy.signal_sell(price_data=price_data, step=step):
            # Add quote asset on the current price
            self.quote_amount += self.base_amount * price_data.loc[step, "close_price"]
            # Sell all our base asset
            self.base_amount -= self.base_amount
            # Update amount of assets we have
            self.assets_amount = [self.base_amount, self.quote_amount]
            # Write info about our assets in to dataframe
            price_data.loc[step, self.assets] = self.assets_amount
            self._strategy.position_open = False
        else:
            # If nothing happen keep writing info about our assets
            price_data.loc[step, self.assets] = self.assets_amount

    def form_report(self, price_data: pd.DataFrame, file_name: str) -> None:
        """Method grabs price data after backtesting, computes info about capital on whole period of backtesting
        and saves report in form of excel file

        :param price_data: dataframe of price data after backtesting
        :param file_name: name of the file in which data will be saved
        """
        price_data["capital"] = price_data[self.quote] + price_data[self.base] * price_data["close_price"]
        price_data["close_time"] = price_data["close_time"].dt.tz_localize(None)
        # Create directory for reports (if not exists)
        dir_name = "../crypt_bot/back_test_files/"
        try:
            os.makedirs(dir_name)
            print("Directory ", dir_name, " Created ")
        except FileExistsError:
            print("Directory ", dir_name, " already exists")
        price_data.to_excel(dir_name + file_name + "backtest.xlsx")
