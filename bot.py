import asyncio
from asyncio.windows_events import NULL
import os
from discord import channel

from pymongo import MongoClient

from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json
import ccxt

from discord.ext import commands
from dotenv import load_dotenv
import user

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
API_KEY = os.getenv('API_KEY')
DATABASE = os.getenv('DATABASE')

# connect to MongoDB (configured in env)
cluster = MongoClient(os.getenv('CONNECTION_URL'))
db = cluster[DATABASE]

bot = commands.Bot(command_prefix=os.getenv(
    'COMMAND_PREFIX'), help_command=None)

isaacID = 234450128008642571
pizzaManID = 535610244894556209
generalChannelID = 297137345730314242

USERS = []


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')


def get_usd_for_symbol(symbol):
    print('Getting price for symbol: ' + symbol)
    exchange = ccxt.binance()
    exchange.load_markets()
    ticker = symbol + '/USDT'
    if ticker in exchange.markets.keys():
        ticker = exchange.fetch_ticker(ticker)
        usd = (float(ticker['info']['askPrice']) +
               float(ticker['info']['bidPrice'])) / 2
        change = float(ticker['info']['priceChangePercent'])
    else:
        usd = None
        change = None
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        parameters = {
            'symbol': symbol,
            'convert': 'USD'
        }
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': API_KEY,
        }

        session = Session()
        session.headers.update(headers)

        try:
            response = session.get(url, params=parameters)
            data = json.loads(response.text)
            print(data)
            if data.get('status').get('error_message') is None:
                usd = data.get('data').get(symbol.upper()).get(
                    'quote').get('USD').get('price')
                change = data.get('data').get(symbol.upper()).get(
                    'quote').get('USD').get('percent_change_24h')
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            print(e)

    return usd, change


def get_number_of_coins(symbol, usd):
    return usd / get_usd_for_symbol(symbol)[0]


def get_cost_of_coins(symbol, amount):
    return amount * get_usd_for_symbol(symbol)[0]


@bot.command(name='price')
async def price(ctx, symbol):
    print('Got price command from: ' + ctx.author.name)
    usd, change = get_usd_for_symbol(symbol)
    if usd is not None:
        change_formatted = ("{:.1f}".format(change), "+" +
                            "{:.1f}".format(change))[change > 0]
        await ctx.send(f"{symbol} price: ${str(usd)} ({change_formatted}%)")
    else:
        await ctx.send(f"Could not find crypto with symbol {symbol}")


@bot.command(name='buy')
async def buy(ctx, symbol, amount):
    print(f"Got buy command from: {ctx.author.name}")
    users = db['users']
    query = {"_id": ctx.author.id}
    result = users.find_one(query)
    if amount == 'max':
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
            print(
                f"Checking for entry in {owned.name} for user {ctx.author.id}, symbol {symbol}")
            query = {"user_id": ctx.author.id, "symbol": symbol}
            result = owned.find_one(query)
            number_of_coins = get_number_of_coins(symbol, total)
            if result is None:
                post = {"user_id": ctx.author.id,
                        "symbol": symbol, "amount": number_of_coins}
                owned.insert_one(post)
                print(
                    f"Added new record for user {ctx.author.id}, symbol {symbol}, amount {number_of_coins}")
            else:
                new_coin_total = result['amount'] + number_of_coins
                update = {"$set": {"amount": new_coin_total}}
                owned.update_one(query, update)
                print(
                    f"Updated record for user {ctx.author.id}, symbol {symbol}, amount {new_coin_total}")

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
    print('Got sell command from: ' + ctx.author.name)
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
                print(
                    f"Updated owned record for user {ctx.author.id}, symbol {symbol}, amount {new_coin_total}")

                # increase user balance
                users = db['users']
                query = {'_id': ctx.author.id}
                this_user = users.find_one(query)
                new_balance_total = this_user['balance'] + price_of_coins
                update = {"$set": {'balance': new_balance_total}}
                users.update_one(query, update)
                print(
                    f"Updated users record for user {ctx.author.id} balance {new_balance_total}")

                new_balance_total_formatted = "{:.2f}".format(
                    new_balance_total)
                await ctx.send(f"{ctx.author.name} successfully sold {coins} {symbol}.\n"
                               f"Current {symbol} balance: {new_coin_total} coins.\n"
                               f"Current cash balance: ${new_balance_total_formatted}")
            else:
                await ctx.send(f"{ctx.author.name} does not own enough {symbol} to sell {amount} coins. "
                               f"Current {symbol} balance: {result['amount']} coins.")


@bot.command(name='balance')
async def balance(ctx, symbol=None):
    print(f"Got balance command from: {ctx.author.name}")
    if symbol is None:
        users = db['users']
        query = {"_id": ctx.author.id}
        this_user = users.find_one(query)
        if this_user is None:
            print(f"Attempting to add user {ctx.author.id} to DB")
            post = {"_id": ctx.author.id,
                    "name": ctx.author.name, 'balance': 5000}
            users.insert_one(post)
            print(f"Added user to DB: {post}")
            await ctx.send(f"{ctx.author.name} has joined crypto paper trading! Your cash balance is $5000.00")
        else:
            print(f"Getting user {ctx.author.id} balance")
            usd = "{:.2f}".format(this_user['balance'])

            owned = db['owned']
            cryptos = "\n"
            total = 0
            for crypto in owned.find({'user_id': ctx.author.id}, {'_id': 0, 'symbol': 1, 'amount': 1}):
                if crypto['amount'] != 0:
                    value = crypto['amount'] * \
                        get_usd_for_symbol(crypto['symbol'])[0]
                    total += value
                    value_formatted = "{:.2f}".format(value)
                    cryptos += f"{crypto['symbol']}: ${value_formatted}\n"
            cryptos = cryptos[0:len(cryptos) - 1]
            total += this_user['balance']
            total_formatted = "{:.2f}".format(total)

            if cryptos == "":
                await ctx.send(f"{ctx.author.name}'s cash balance is ${usd}")
            else:
                await ctx.send(f"{ctx.author.name}'s cash balance is ${usd}, net worth is ${total_formatted}\n"
                               f"Current cryptos owned: {cryptos}")
    else:
        owned = db['owned']
        query = {"user_id": ctx.author.id, "symbol": symbol}
        result = owned.find_one(query)
        if result is None:
            await ctx.send(f"{ctx.author.name} does not own crypto with symbol {symbol}")
        else:
            crypto_balance = result['amount']
            usd = "{:.2f}".format(get_cost_of_coins(symbol, crypto_balance))
            await ctx.send(f"{ctx.author.name} owns {crypto_balance} coins of {symbol}, worth ${usd}")


@bot.command(name='leaderboard')
async def leaderboard(ctx):
    print(f"Got leaderboard command from: {ctx.author.name}")
    # get all user ids
    users = db['users']
    all_users = {}
    found_price = {}
    for this_user in users.find():
        owned = db['owned']
        total = 0
        for crypto in owned.find({'user_id': this_user['_id']}):
            if crypto['symbol'] in found_price:
                total += found_price[crypto['symbol']] * crypto['amount']
            else:
                crypto_price = get_usd_for_symbol(crypto['symbol'])[0]
                found_price[crypto['symbol']] = crypto_price
                total += crypto_price * crypto['amount']
        all_users[this_user['name']] = this_user['balance'] + total
    sorted_users = sorted(
        all_users.items(), key=lambda kv: kv[1], reverse=True)
    print(f"Got leaderboard: {sorted_users}")

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

# @bot.command(name='sell_all')
# async def sell_all(ctx):
#     await ctx.send(f"Are you sure you want to sell everything {ctx.author.name}? (y / n)")

#     def check(msg):
#         return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.lower()

#     try:
#         msg = await bot.wait_for("message", check=check, timeout=15)
#         if msg.content.lower() == "y":
#             await ctx.send("You said yes!")
#             #TODO Code the shit you idiot
#         else:
#             await ctx.send("You did not say yes!")
#     except asyncio.TimeoutError:
#         await ctx.send("You took too long you fucking idiot.", tts=True)


@bot.event
async def on_voice_state_update(member, before, after):
    # Get general channel id
    channel = bot.get_channel(generalChannelID)
    try:
        if after.channel.members is not None:
            # Check if isaac joined a voice channel
            if member.id == (isaacID):
                # Say mean things
                await channel.send("Isaac Dumitru is a stinky poopy stupid head.", tts=True)
    except Exception:
        # Need to check if after.members exisits but this works fine for now
        print("idk it works tho")


@bot.event
async def on_message(message):
    # Check if this message is a command, and if it is evaluate it
    await bot.process_commands(message)

bot.run(TOKEN)
