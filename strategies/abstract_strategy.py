from abc import ABC, abstractmethod


class AbstractStrategy(ABC):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @abstractmethod
    def set_settings(self, short_term, long_term, client):
        pass

    @abstractmethod
    def run(self, interval, stream_id):
        pass

    @abstractmethod
    def test_buy(self, price_data, step):
        pass

    @abstractmethod
    def test_sell(self, price_data, step):
        pass

    @abstractmethod
    def stop(self):
        pass
