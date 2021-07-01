from datetime import datetime
from strategies.start_strategy import StartStrategy
from strategies.sma_strategy import SMAStrategy
from exchange.binanceclient import BinanceAPIClient

list_of_commands = ["help", "quit", "live", "test", "back_test"]


def bot_help():
    print("Main commands:")
    print("     help        show help")
    print("     quit        quit program")
    print("")
    print("     live        start real trading")
    print("     test        start live trading on binance spot testnet")
    print("     back_test   start backtester")


def back_test_start():
    print("***** Start backtesting! *****")
    base_asset = input("Please enter base asset (for example 'USD'): ").upper()
    print("available candle intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M\n"
          "m -> minutes; h -> hours; d -> days; w -> weeks; M -> months")
    candle_interval = input("Please enter candle interval: ")
    short_term, long_term = input("Please enter short and long terms for moving average "
                                  "in form 'short_term long_term': ").split(" ")
    trading_capital = float(input("Please enter a part of your capital that going to be used in trading\n"
                                  "(example - 0.2): "))
    start_year, start_month, start_day  = input("Please enter start day of back testing "
                                                "in format yyyy-mm-dd: ").split("-")
    end_year, end_month, end_day = input("Please enter end day of back testing "
                                         "in format yyyy-mm-dd: ").split("-")
    start_date = datetime(year=int(start_year), month=int(start_month), day=int(start_day))
    end_date = datetime(year=int(end_year), month=int(end_month), day=int(end_day))
    quote_asset_amount = float(input("Please enter how much quote asset you have for back test: "))
    short_term_int = int(short_term)
    long_term_int = int(long_term)
    strategy = SMAStrategy(short_term=short_term_int, long_term=long_term_int,
                           trading_capital=trading_capital, candle_interval=candle_interval)
    back_test = StartStrategy(strategy=strategy, mode="BACK_TEST")
    back_test.set_backtester_settings(start_day=start_date, end_day=end_date,
                                      base_asset=base_asset, quote_asset="USDT",
                                      quote_asset_amount=quote_asset_amount)
    back_test.start()
    print("Back test executed!")


def test_trading_start():
    print("***** Trading on spot testnet will be executed! *****")
    while True:
        confirm = input("Do you want to continue and start real trading? [y/n]: ").lower()
        if confirm == "y":
            mode = "test"
            client = initialize_client(mode)
            strategy = initialize_strategy()
            bot_interface = StartStrategy(client=client, strategy=strategy, mode="TEST")
            bot_interface.start()
        elif confirm == "n":
            main()
        else:
            print("Try to print 'y' or 'n'")


def trading_start():
    print("***** Caution! Real trading will be executed! *****")
    while True:
        confirm = input("Do you want to continue and start real trading? [y/n]: ").lower()
        if confirm == "y":
            mode = "prod"
            client = initialize_client(mode)
            strategy = initialize_strategy()
            bot_interface = StartStrategy(client=client, strategy=strategy, mode="LIVE")
            bot_interface.start()
        elif confirm == "n":
            main()
        else:
            print("Try to print 'y' or 'n'")


def initialize_strategy() -> SMAStrategy:
    print("Initializing simple moving average strategy")
    print("available candle intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M\n"
          "m -> minutes; h -> hours; d -> days; w -> weeks; M -> months")
    candle_interval = input("Please enter candle interval: ")
    short_term, long_term = input("Please enter short and long terms for moving average "
                                  "in form 'short_term long_term': ").split(" ")
    trading_capital = float(input("Please enter a fraction of your capital that going to used in trading\n"
                                  "(example - 0.2): "))
    losses = float(input("Please enter fraction of capital you accept to lose: "))
    short_term_int = int(short_term)
    long_term_int = int(long_term)
    return SMAStrategy(short_term=short_term_int, long_term=long_term_int,
                       trading_capital=trading_capital,
                       losses=losses,
                       candle_interval=candle_interval)


def initialize_client(mode="test") -> BinanceAPIClient:
    print("Initializing Binance API Client")
    if mode == "prod":
        api_key = input("Please enter your Binance API KEY: ")
        secret_key = input("Please enter your Binance SECRET KEY: ")
    elif mode == "test":
        api_key = input("Please enter your Binance API KEY for spot testnet: ")
        secret_key = input("Please enter your Binance SECRET KEY for spot testnet: ")
    else:
        api_key = ""
        secret_key = ""
    base_asset = input("Please enter base asset (for example 'btc'): ").upper()
    return BinanceAPIClient(base_asset=base_asset, quote_asset="USDT",
                            api_key=api_key, secret_key=secret_key, mode=mode)


def command_handler(command: str):
    if command == "quit":
        return False
    elif command == "help":
        bot_help()
        return True
    elif command == "live":
        trading_start()
        return True
    elif command == "test":
        test_trading_start()
        return True
    elif command == "back_test":
        back_test_start()
        return True


def main():
    bot_run = True
    while bot_run:
        command = input("crypt_bot> ").lower()
        if command in list_of_commands:
            bot_run = command_handler(command)
        else:
            print("Wrong command. Try 'help' command for information")


if __name__ == "__main__":
    try:
        bot_help()
        main()
    except Exception as e:
        print("Error: ", e)
        main()
