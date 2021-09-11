class Prices:

    def __init__(self):
        self.PRICES = {}

    def get_price(self, symbol):
        return self.PRICES[symbol]

    def set_prices(self, values):
        self.PRICES = values