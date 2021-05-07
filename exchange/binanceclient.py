import requests
from datetime import timedelta
import csv
import pandas as pd
import numpy as np


class BinanceAPIClient(Exception):
    base_asset: str
    quote_asset: str

    def __init__(self, base_asset, quote_asset):
        self.base = base_asset
        self.quote = quote_asset
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

    def get_candlestick(self, time_interval=None, candles_interval="1m", depth=500) -> list:
        """
        :param time_interval: in minutes
        :param candles_interval: m -> minutes; h -> hours; d -> days; w -> weeks; M -> months
        1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        :param depth: max 1000
        :return:
        """
        if time_interval is None:
            params = {"symbol": self.pair, "interval": candles_interval, "limit": depth}
        else:
            end = BinanceAPIClient.get_server_time()
            start = end - timedelta(minutes=time_interval).total_seconds() * 1000
            params = {"symbol": self.pair, "interval": candles_interval,
                      "startTime": int(start), "endTime": int(end), "limit": 1000}
        resp = requests.get("https://api.binance.com/api/v3/klines", params=params)
        return resp.json()

    def get_pandas_df(self, time_interval=None, candles_interval="1m", depth=500):
        data_for_df = self.get_candlestick(time_interval=time_interval,
                                           candles_interval=candles_interval,
                                           depth=depth)
        data_for_df = [[self.base, self.quote] + x for x in data_for_df]
        df_headers = ['base_asset', 'quote_asset', 'open_time',
                      'open', 'high', 'low', 'close', 'volume',
                      'close_time', 'quote_asset_volume', 'number_of_trades',
                      'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
        return pd.DataFrame(np.array(data_for_df), columns=df_headers)

    def save_csv(self, time_interval=None, candles_interval="1m", depth=500):
        data_for_csv = self.get_candlestick(time_interval=time_interval,
                                            candles_interval=candles_interval,
                                            depth=depth)
        data_for_csv = [[self.base, self.quote] + x for x in data_for_csv]
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
