import csv
import requests
import numpy as np
import pandas as pd
from supp_script import get_intervals
from datetime import datetime, timezone


class BinanceAPIClient(Exception):
    base_asset: str
    quote_asset: str

    def __init__(self, base_asset, quote_asset):
        self.base = base_asset
        self.quote = quote_asset
        self.candlestick = []
        self.pair = self._get_pair()
        self._chek_pair()

    def _get_pair(self):
        return self.base + self.quote

    def _chek_pair(self):
        data = []
        with open("all_pairs.txt", "r") as f:
            for line in f:
                data.append(line.rstrip("\n"))
            if self.pair not in data:
                raise Exception("There is no pair " + self.pair + " in Binance exchange")

    def get_candlestick(self, candles_interval: str = "1m", depth=500):
        """
        :param candles_interval: m -> minutes; h -> hours; d -> days; w -> weeks; M -> months
        1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        :param depth: max 1000
        :return:
        """
        BinanceAPIClient._chek_interval(candles_interval)
        params = {"symbol": self.pair, "interval": candles_interval, "limit": depth}
        resp = requests.get("https://api.binance.com/api/v3/klines", params=params)
        self.candlestick = resp.json()

    def get_candlestick_for_given_time(self, start_y, start_m, start_d,
                                       end_y, end_m, end_d, candles_interval: str = "1m"):
        intervals = ["1m", "3m", "5m", "15m", "30m",
                     "1h", "2h", "4h", "6h", "8h", "12h",
                     "1d", "3d", "1w", "1M"]
        BinanceAPIClient._chek_interval(candles_interval)
        delta = get_intervals(intervals)[candles_interval]
        start_date = datetime(start_y, start_m, start_d).replace(tzinfo=timezone.utc).timestamp() * 1000
        end_date = datetime(end_y, end_m, end_d).replace(tzinfo=timezone.utc).timestamp() * 1000
        data = []
        while start_date < end_date:
            if start_date + 1000 * delta < end_date:
                params = {"symbol": self.pair, "startTime": int(start_date),
                          "endTime": int(start_date + 1000 * delta), "interval": candles_interval, "limit": 1000}
                start_date += 1000 * delta
                resp = requests.get("https://api.binance.com/api/v3/klines", params=params)
                data += resp.json()
            else:
                params = {"symbol": self.pair, "startTime": int(start_date),
                          "endTime": int(end_date), "interval": candles_interval, "limit": 1000}
                start_date += 1000 * delta
                resp = requests.get("https://api.binance.com/api/v3/klines", params=params)
                data += resp.json()
        self.candlestick = data

    def get_pandas_df(self):
        data_for_df = [[self.base, self.quote] + x for x in self.candlestick]
        df_headers = ['base_asset', 'quote_asset', 'open_time',
                      'open', 'high', 'low', 'close', 'volume',
                      'close_time', 'quote_asset_volume', 'number_of_trades',
                      'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
        return pd.DataFrame(np.array(data_for_df), columns=df_headers).drop(['ignore'], axis=1)

    def save_csv(self):
        data_for_csv = [[self.base, self.quote] + x for x in self.candlestick]
        csv_headers = ['base_asset', 'quote_asset', 'open_time',
                       'open', 'high', 'low', 'close', 'volume',
                       'close_time', 'quote_asset_volume', 'number_of_trades',
                       'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
        with open(self.pair + ".csv", 'w', newline='') as f:
            csv_writer = csv.writer(f, delimiter=',')
            csv_writer.writerow(csv_headers)
            csv_writer.writerows(data_for_csv)

    @staticmethod
    def get_server_time():
        resp = requests.get("https://api.binance.com/api/v3/time")
        return resp.json()['serverTime']

    @staticmethod
    def _chek_interval(interval):
        intervals = ["1m", "3m", "5m", "15m", "30m",
                     "1h", "2h", "4h", "6h", "8h", "12h",
                     "1d", "3d", "1w", "1M"]
        if interval not in intervals:
            raise Exception("candles_interval must be one of the strings: " + ', '.join(intervals))
