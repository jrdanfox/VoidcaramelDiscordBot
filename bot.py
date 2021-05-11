import os

from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json

from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime
from user import User

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
API_KEY = os.getenv('API_KEY')

bot = commands.Bot(command_prefix='!')

USERS = []


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')


def get_usd_for_symbol(symbol):
    print('Getting price for symbol: ' + symbol)
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
            usd = data.get('data').get(symbol).get('quote').get('USD').get('price')
            change = data.get('data').get(symbol).get('quote').get('USD').get('percent_change_24h')
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
        change_formatted = ("{:.1f}".format(change), "+" + "{:.1f}".format(change))[change > 0]
        await ctx.send(f"{symbol} price: ${str(usd)} ({change_formatted}%)")
    else:
        await ctx.send(f"Could not find crypto with symbol {symbol}")


@bot.command(name='buy')
async def buy(ctx, symbol, amount: float):
    print('Got buy command from: ' + ctx.author.name)
    for user in USERS:
        if user.get_user_id() == ctx.author.id:
            if amount <= 0:
                await ctx.send("Cannot buy 0 or fewer coins.")
            else:
                number_of_coins = get_number_of_coins(symbol, amount)
                purchase = user.purchase(symbol, number_of_coins, amount)
                if purchase != "success":
                    await ctx.send(purchase)
                else:
                    balance_formatted = "{:.2f}".format(user.get_balance())
                    amount_formatted = "{:.2f}".format(amount)
                    await ctx.send(f"{user.name} bought {amount_formatted} USD of {symbol}, "
                                   f"{number_of_coins} coins. Remaining balance: ${balance_formatted}")


@bot.command(name='sell')
async def sell(ctx, symbol, amount):
    print('Got sell command from: ' + ctx.author.name)
    for user in USERS:
        if user.get_user_id() == ctx.author.id:
            if amount == 'max':  # sell all of the coins
                coins = user.get_balance_of_coin(symbol)
            else:
                coins = float(amount)
            if coins <= 0:
                await ctx.send("Cannot sell 0 or fewer coins.")
            else:
                price_of_coins = get_cost_of_coins(symbol, coins)
                message = user.sell(symbol, coins, price_of_coins)
                if message != 'success':
                    await ctx.send(message)
                else:
                    price_of_coins_formatted = "{:.2f}".format(price_of_coins)
                    balance_formatted = "{:.2f}".format(user.get_balance())
                    await ctx.send(f"{user.name} successfully sold {symbol} for ${price_of_coins_formatted}. "
                                   f"Balance: {balance_formatted}")


@bot.command(name='balance')
async def balance(ctx, symbol=None):
    for user in USERS:
        if user.get_user_id() == ctx.author.id:
            if symbol is None:
                usd = "{:.2f}".format(user.get_balance())
                cryptos = ""
                for crypto in user.get_owned_cryptos():
                    cryptos += crypto + ", "
                cryptos = cryptos[0:len(cryptos) - 2]
                if cryptos == "":
                    await ctx.send(f"{user.name}'s cash balance is ${usd}")
                else:
                    await ctx.send(f"{user.name}'s cash balance is ${usd}, current cryptos owned: {cryptos}")
            else:
                crypto_balance = user.get_balance_of_coin(symbol)
                if crypto_balance is not None:
                    usd = "{:.2f}".format(get_cost_of_coins(symbol, crypto_balance))
                    await ctx.send(f"{user.name} owns {crypto_balance} coins of {symbol}, worth ${usd}")
                else:
                    await ctx.send(f"{user.name} does not own crypto with symbol {symbol}")


@bot.command(name='gametime')
async def gametime(ctx):
    print('Got gametime command from: ' + ctx.author.name)
    for user in USERS:
        if user.get_user_id() == ctx.author.id:
            if ctx.author.activity is not None and ctx.author.activity.type.name == 'playing':
                elapsed_time = divmod((datetime.now() - user.current_game_start_time).seconds, 60)
                await ctx.send(f"You've been in {ctx.author.activity.name.strip()} for {str(elapsed_time[0])} minutes, "
                               f"{str(elapsed_time[1])} seconds.")


@bot.event
async def on_message(message):
    # check if this user is in USERS, adds them if not
    if message.author.name != 'VoidcaramelDiscordBot':
        found = False
        for user in USERS:
            if user.user_id == message.author.id:
                found = True
        if not found:
            USERS.append(User(message.author.id, message.author.name))

    # Check if this message is a command, and if it is evaluate it
    await bot.process_commands(message)


@bot.event
async def on_member_update(before, after):
    if before.activity is None:
        print('before.activity is None')
    else:
        print(f'before.activity.type is {before.activity.type}')

    if after.activity is None:
        print('after.activity is None')
    else:
        print(f'after.activity.type is {after.activity.type}')

    if (before.activity is None or not before.activity.type.name == 'playing') and \
            (after.activity is not None and after.activity.type.name == 'playing'):
        updated_member = None
        for user in USERS:
            if user.name == after.name:
                updated_member = user

        if updated_member is None:  # This user is not already in USERS, create a new User and update gametime
            user = User(after.name)
            user.update_game_start_time(datetime.now())
            USERS.append(user)
        else:  # This user is already in USERS, update gametime
            updated_member.update_game_start_time(datetime.now())


bot.run(TOKEN)
