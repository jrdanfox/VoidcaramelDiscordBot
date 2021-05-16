
# TODO: refactor to static, handle users DB interactions here

# def __init__(self, user_id, name):
#     self.user_id = user_id
#     self.name = name
#     self.balance = 5000
#     self.owned = {}

# def does_user_own(symbol):
#     if symbol not in self.owned:
#         return False
#     else:
#         return self.owned[symbol] != 0

# def get_balance_of_coin(symbol):
#     return self.owned[symbol]

# def get_balance(self):
#     return self.balance

# def get_user_id(self):
#     return self.user_id

# def get_owned_cryptos(self):
#     cryptos = []
#     for crypto in self.owned:
#         if self.owned[crypto] != 0:
#             cryptos.append(crypto)
#     return cryptos

# def purchase(self, symbol, amount, price):
#     if price > self.balance:
#         return "You don't have enough balance for this purchase."
#     else:
#         if symbol in self.owned:
#             self.owned[symbol] += amount
#             self.balance -= price
#         else:
#             self.owned[symbol] = amount
#             self.balance -= price
#         return "success"

# def sell(self, symbol, amount, price):
#     if symbol in self.owned:
#         previous = self.owned[symbol]
#         if previous < amount:
#             return f"{self.name} does not own enough {symbol} to sell {amount} coins"
#         else:
#             self.owned[symbol] = previous - amount
#             self.balance += price
#             return 'success'
#     else:
#         return f"{self.name} does not own crypto with symbol {symbol}"
