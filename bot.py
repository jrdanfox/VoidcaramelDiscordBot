import os

import discord
import random
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

client = discord.Client()


@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')


@client.event
async def on_message(message):
    rand = random.randint(0, 100)
    print(f'Message received from: {message.author}')
    print(f'Random number: {rand}')
    if rand % 10 == 0 and message.author.name in ['Arise Matt', 'Isaac Dumitru']:
        await message.channel.send(f'Eat my booty {message.author.mention}')
    if rand == 1 and message.author.name in ['Arise Matt', 'Isaac Dumitru']:
        await message.channel.send(f'You are the definition of birth control {message.author.mention}')

client.run(TOKEN)
