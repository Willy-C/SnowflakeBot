import discord
from discord.ext import commands

import sys, traceback
from typing import Union
import datetime

import error_handler

DESCR = 'This bot is a small side project and still very WIP'
TOKEN = ''
print(error_handler.token22)


def get_prefix(bot, message):
    """A callable Prefix for our bot. This could be edited to allow per server prefixes."""

    # Notice how you can use spaces in prefixes. Try to keep them simple though.
    prefixes = ['>?', 'lol ', '!?']

    # Check to see if we are outside of a guild. e.g DM's etc.
    if not message.guild:
        # Only allow ? to be used in DMs
        return '?'

    # If we are in a guild, we allow for the user to mention us or use any of the prefixes in our list.
    return commands.when_mentioned_or(*prefixes)(bot, message)


bot = commands.Bot(command_prefix=get_prefix, description=DESCR)


@bot.event
async def on_ready():
    print(f'\n\nLogged in as: {bot.user.name} - {bot.user.id}\n'
          f'Version: {discord.__version__}\n')

    activity = discord.Activity(type=discord.ActivityType.listening, name='you :)')
    await bot.change_presence(activity=activity)
    print(f'Ready! {datetime.datetime.now()}')


bot.run(TOKEN, bot=True, reconnect=True)
