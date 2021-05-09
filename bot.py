import os
import random

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


@bot.command(name='price')
async def price(ctx, symbol):
    print('Got price command from: ' + ctx.author.name)
    print('Getting price for symbol: ' + symbol)
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
        price = data.get('data').get(symbol).get('quote').get('USD').get('price')
        await ctx.send(symbol + " price: $" + str(price))
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)


@bot.command(name='gametime')
async def gametime(ctx):
    print('Got gametime command from: ' + ctx.author.name)
    for user in USERS:
        if user.name == ctx.author.name:
            if ctx.author.activity is not None and ctx.author.activity.type.name == 'playing':
                elapsed_time = divmod((datetime.now() - user.current_game_start_time).seconds, 60)
                await ctx.send(f"You've been in {ctx.author.activity.name.strip()} for {str(elapsed_time[0])} minutes, "
                               f"{str(elapsed_time[1])} seconds.")

@bot.command(name='dad')
async def dad(ctx):
    rand = random.randint(0, 100)
    await ctx.channel.send(f"Dallas' dad has been at the store for %d years" % (rand / 4))

@bot.event
async def on_message(message):
    # Check if this message is a command, and if it is evaluate it
    await bot.process_commands(message)

    rand = random.randint(0, 100)
    print(f'Message received from: {message.author}')
    print(f'Random number: {rand}')
    if rand % 10 == 0 and message.author.name in ['Arise Matt', 'Isaac Dumitru']:
        await message.channel.send(f'Eat my booty {message.author.mention}')
    if rand == 1 and message.author.name in ['Arise Matt', 'Isaac Dumitru']:
        await message.channel.send(f'You are the definition of birth control {message.author.mention}')

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
