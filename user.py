class User:

    def __init__(self, name):
        self.name = name
        self.balance = 5000
        self.current_game_start_time = None
        self.owned = {}

    def update_game_start_time(self, gametime):
        self.current_game_start_time = gametime

    def get_balance_of_coin(self, symbol):
        return self.owned[symbol]

    def get_balance(self):
        return self.balance

    def get_owned_cryptos(self):
        cryptos = []
        for crypto in self.owned:
            if self.owned[crypto] != 0:
                cryptos.append(crypto)
        return cryptos

    def purchase(self, symbol, amount, price):
        if symbol in self.owned:
            return "You already own this crypto."
        else:
            if price > self.balance:
                return "You don't have enough balance for this purchase."
            else:
                self.owned[symbol] = amount
                self.balance -= price
                return "success"

    def sell(self, symbol, amount, price):
        if symbol in self.owned:
            previous = self.owned[symbol]
            if previous < amount:
                return f"{self.name} does not own enough {symbol} to sell {amount} coins"
            else:
                self.owned[symbol] = previous - amount
                self.balance += price
                return 'success'
        else:
            return f"{self.name} does not own crypto with symbol {symbol}"
