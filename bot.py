import os
import sys
import logging
import ccxt
from prices import Prices
from pymongo import MongoClient
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(format='%(asctime)s - %(message)s',
                    stream=sys.stdout,
                    level=logging.INFO)

TOKEN = os.getenv('DISCORD_TOKEN')
DATABASE = os.getenv('DATABASE')

# connect to MongoDB (configured in env)
cluster = MongoClient(os.getenv('CONNECTION_URL'))
db = cluster[DATABASE]

bot = commands.Bot(command_prefix=os.getenv('COMMAND_PREFIX'),
                   help_command=None)

PRICES = Prices()


@tasks.loop(seconds=10)
async def populate_crypto_prices():
    users = db['users']
    owned = db['owned']
    cryptos = []
    for user in users.find():
        for crypto in owned.find({'user_id': user['_id'], 'amount': {'$gt': 0}}):
            if crypto not in cryptos:
                cryptos.append(crypto['symbol'])

    logging.info(f'Fetching exchange info')
    exchange = ccxt.binance()
    exchange.load_markets()
    tickers = []
    values = {}  # ticker -> usd, change
    for symbol in cryptos:
        ticker = symbol + '/USDT'
        tickers.append(ticker)
    tickers = exchange.fetch_tickers(tickers)
    logging.info(f'Getting price for tickers: {tickers}')
    for ticker in tickers:
        usd = (float(tickers[ticker]['info']['askPrice']) + float(tickers[ticker]['info']['bidPrice'])) / 2
        change = float(tickers[ticker]['info']['priceChangePercent'])
        values[ticker.replace('/USDT', '')] = usd, change
    logging.info(f'Got prices: {values}')

    PRICES.set_prices(values)


@bot.event
async def on_ready():
    logging.info(f'{bot.user} has connected to Discord!')


def get_usd_for_symbols(symbols):
    usd_values = {}
    for symbol in symbols:
        usd_values[symbol] = PRICES.get_price(symbol)
    return usd_values


def get_number_of_coins(symbol, usd):
    return usd / get_usd_for_symbols([symbol])[symbol][0]


def get_cost_of_coins(symbol, amount):
    return amount * get_usd_for_symbols([symbol])[symbol][0]


@bot.command(name='price')
async def price(ctx, symbol):
    logging.info('Got price command from: ' + ctx.author.name)
    usd, change = get_usd_for_symbols([symbol])
    if usd is not None:
        change_formatted = ("{:.1f}".format(change), "+" + "{:.1f}".format(change))[change > 0]
        await ctx.send(f"{symbol} price: ${str(usd)} ({change_formatted}%)")
    else:
        await ctx.send(f"Could not find crypto with symbol {symbol}")


@bot.command(name='buy')
async def buy(ctx, symbol, amount):
    logging.info(f"Got buy command from: {ctx.author.name}")
    users = db['users']
    query = {"_id": ctx.author.id}
    result = users.find_one(query)
    if amount.lower() == 'max':
        total = result['balance']
    else:
        total = float(amount)
    if total <= 0:
        await ctx.send("Cannot buy 0 or fewer coins.")
    else:
        # decrease balance
        users = db["users"]
        query = {"_id": ctx.author.id}
        this_user = users.find_one(query)
        if this_user['balance'] >= total:
            new_balance_total = this_user['balance'] - total
            update = {"$set": {'balance': new_balance_total}}
            users.update_one(query, update)

            # increase coins
            owned = db["owned"]
            logging.info(f"Checking for entry in {owned.name} for user {ctx.author.id}, symbol {symbol}")
            query = {"user_id": ctx.author.id, "symbol": symbol}
            result = owned.find_one(query)
            number_of_coins = get_number_of_coins(symbol, total)
            if result is None:
                post = {"user_id": ctx.author.id, "symbol": symbol, "amount": number_of_coins}
                owned.insert_one(post)
                logging.info(f"Added new record for user {ctx.author.id}, symbol {symbol}, amount {number_of_coins}")
            else:
                new_coin_total = result['amount'] + number_of_coins
                update = {"$set": {"amount": new_coin_total}}
                owned.update_one(query, update)
                logging.info(f"Updated record for user {ctx.author.id}, symbol {symbol}, amount {new_coin_total}")

            balance_formatted = "{:.2f}".format(new_balance_total)
            amount_formatted = "{:.2f}".format(total)
            await ctx.send(f"{this_user['name']} bought {amount_formatted} USD of {symbol}, "
                           f"{number_of_coins} coins. Remaining balance: ${balance_formatted}")
        else:
            balance_formatted = "{:.2f}".format(this_user['balance'])
            await ctx.send(f"{this_user['name']} doesn't have enough balance for this purchase. "
                           f"Balance: ${balance_formatted}")


@bot.command(name='sell')
async def sell(ctx, symbol, amount):
    logging.info('Got sell command from: ' + ctx.author.name)
    owned = db['owned']
    query = {"user_id": ctx.author.id, "symbol": symbol}
    result = owned.find_one(query)
    if result is None:
        await ctx.send(f"{ctx.author.name} does not own crypto with symbol {symbol}")
    else:
        if amount == 'max':
            coins = result['amount']
        else:
            coins = float(amount)
        if coins <= 0:
            await ctx.send("Cannot sell 0 or fewer coins.")
        else:
            if result['amount'] >= coins:
                price_of_coins = get_cost_of_coins(symbol, coins)
                # decrease user coin count
                new_coin_total = result['amount'] - coins
                update = {"$set": {"amount": new_coin_total}}
                owned.update_one(query, update)
                logging.info(f"Updated owned record for user {ctx.author.id}, symbol {symbol}, amount {new_coin_total}")

                # increase user balance
                users = db['users']
                query = {'_id': ctx.author.id}
                this_user = users.find_one(query)
                new_balance_total = this_user['balance'] + price_of_coins
                update = {"$set": {'balance': new_balance_total}}
                users.update_one(query, update)
                logging.info(f"Updated users record for user {ctx.author.id} balance {new_balance_total}")

                new_balance_total_formatted = "{:.2f}".format(new_balance_total)
                await ctx.send(f"{ctx.author.name} successfully sold {coins} {symbol}.\n"
                               f"Current {symbol} balance: {new_coin_total} coins.\n"
                               f"Current cash balance: ${new_balance_total_formatted}")
            else:
                await ctx.send(f"{ctx.author.name} does not own enough {symbol} to sell {amount} coins. "
                               f"Current {symbol} balance: {result['amount']} coins.")


@bot.command(name='balance')
async def balance(ctx, symbol=None):
    logging.info(f"Got balance command from: {ctx.author.name}")
    user = None
    if symbol is None:
        users = db['users']
        query = {"_id": ctx.author.id}
        this_user = users.find_one(query)
        if this_user is None:
            logging.info(f"Attempting to add user {ctx.author.id} to DB")
            post = {"_id": ctx.author.id, "name": ctx.author.name, 'balance': 5000}
            users.insert_one(post)
            logging.info(f"Added user to DB: {post}")
            await ctx.send(f"{ctx.author.name} has joined crypto paper trading! Your cash balance is $5000.00")
        else:
            user = this_user
    else:
        owned = db['owned']
        query = {"user_id": ctx.author.id, "symbol": symbol}
        result = owned.find_one(query)
        if result is None:
            users = db['users']
            query = {"name": symbol}
            this_user = users.find_one(query)
            if this_user is None:
                await ctx.send(f"{ctx.author.name} does not own crypto with symbol {symbol}")
            else:
                user = this_user
        else:
            crypto_balance = result['amount']
            usd = "{:.2f}".format(get_cost_of_coins(symbol, crypto_balance))
            await ctx.send(f"{ctx.author.name} owns {crypto_balance} coins of {symbol}, worth ${usd}")
    if user is not None:
        logging.info(f"Getting user {user['_id']} balance")
        usd = "{:.2f}".format(user['balance'])

        owned = db['owned']
        cryptos = "\n"
        total = 0
        owned_cryptos = {}
        for crypto in owned.find({'user_id': user['_id'], 'amount': {'$gt': 0}}, {'_id': 0, 'symbol': 1, 'amount': 1}):
            owned_cryptos[crypto['symbol']] = crypto['amount']
        owned_crypto_prices = get_usd_for_symbols(owned_cryptos.keys())
        for crypto in owned_cryptos:
            value = owned_cryptos[crypto] * owned_crypto_prices[crypto][0]
            total += value
            value_formatted = "{:.2f}".format(value)
            cryptos += f"{crypto}: ${value_formatted}\n"
        cryptos = cryptos[0:len(cryptos) - 1]
        total += user['balance']
        total_formatted = "{:.2f}".format(total)

        if cryptos == "":
            await ctx.send(f"{user['name']}'s cash balance is ${usd}")
        else:
            await ctx.send(f"{user['name']}'s cash balance is ${usd}, net worth is ${total_formatted}\n"
                           f"Current cryptos owned: {cryptos}")


@bot.command(name='leaderboard')
async def leaderboard(ctx):
    logging.info(f"Got leaderboard command from: {ctx.author.name}")
    # get all user ids
    users = db['users']
    all_users = {}  # user -> total money
    crypto_prices = []
    user_owned = {}  # (user, symbol) -> amount
    for this_user in users.find():
        owned = db['owned']
        all_users[this_user['name']] = this_user['balance']
        for crypto in owned.find({'user_id': this_user['_id'], 'amount': {'$gt': 0}}):
            if crypto not in crypto_prices:
                crypto_prices.append(crypto['symbol'])
            user_owned[(this_user['name'], crypto['symbol'])] = crypto['amount']

    crypto_prices = get_usd_for_symbols(crypto_prices)
    for user, symbol in user_owned:
        all_users[user] = all_users[user] + (crypto_prices[symbol][0] * user_owned[user, symbol])

    sorted_users = sorted(all_users.items(), key=lambda kv: kv[1], reverse=True)
    logging.info(f"Got leaderboard: {sorted_users}")

    leaderboard_message = "Current standings:\n"
    for participant in sorted_users:
        formatted_total = "{:.2f}".format(participant[1])
        leaderboard_message += f"{participant[0]} - ${formatted_total}\n"
    await ctx.send(leaderboard_message[0:len(leaderboard_message) - 1])


@bot.command(name='help')
async def print_help(ctx):
    help_message = "Welcome to the crypto paper trading bot. To start playing, use the !balance command to check " \
                   "your balance and start investing in crypto.\n" \
                   "\n" \
                   "**Commands:**\n" \
                   "\n" \
                   "!buy <symbol> <amount> - buy <amount> USD of crypto with symbol <symbol>. We are using " \
                   "CoinMarketCap to check prices, so make sure your crypto is listed there!\n" \
                   "\n" \
                   "!sell <symbol> <amount> - sell <amount> coins of crypto with symbol <symbol>.\n" \
                   "\n" \
                   "!balance - check your cash balance and get a list of the cryptos you currently own. This is also " \
                   "how new users enroll and start playing.\n" \
                   "\n" \
                   "!balance <symbol> - check your current holdings of crypto with symbol <symbol>.\n" \
                   "\n" \
                   "!price <symbol> - get the price of the crypto with symbol <symbol> (via CoinMarketCap)."

    await ctx.send(help_message)


@bot.event
async def on_message(message):
    # Check if this message is a command, and if it is evaluate it
    await bot.process_commands(message)


populate_crypto_prices.before_loop(bot.wait_until_ready)
populate_crypto_prices.start()
bot.run(TOKEN)
