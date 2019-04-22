import discord
from discord.ext import commands

import sys, traceback, platform
from typing import Union
import datetime

from config import BOT_TOKEN

import json

DESCR = 'This bot is a small side project and still very WIP'
TOKEN = BOT_TOKEN

# File names of extensions we are loading on startup
startup_extensions = ['jishaku',
                      'cogs.error_handler',
                      'cogs.members',
                      'cogs.owner',
                      'cogs.metautil',
                      'cogs.avatar',
                      #'cogs.logger',
                      'cogs.random',
                      'cogs.googleimage',
                      'cogs.charinfo',
                      'cogs.fun',
                      'cogs.music',
                      'cogs.setprefix']

custom_prefix = {386406482888884226: ['%']}  # Need to store it somewhere else, will do later
# prefix_map_file = open("data/prefix_map.json", "r+")  # temp var that represents the file itself, not the map
# prefix_map = json.loads(prefix_map_file.read())  # object that actually is the prefix map

with open("data/prefix_map.json") as prefix_map_file:
    # global prefix_map
    prefix_map = json.load(prefix_map_file)


def init_prefixes(bot, message):
    """A callable Prefix for our bot. This could be edited to allow per server prefixes."""

    prefixes = ['?', '%']

    # # Check to see if we are outside of a guild. e.g DM's etc.
    if not message.guild:  # Only allow these to be used in DMs
        return ['?', '%', '$']

    return bot.prefix_map.get(str(message.guild.id), prefixes)  # get the list associated with id, or default to @prefixes


bot = commands.Bot(command_prefix=init_prefixes, description=DESCR)
bot.prefix_map = prefix_map  # define prefix_map as bot variable

def get_prefixes(bot_input, some_id):
    if bot_input.get_guild(some_id) is None:  # passed in a channel id, so probably dms
        return ['?', '%', '$']

    return bot_input.prefix_map.get(str(some_id), ['?', '%'])  # get the list associated with id, or default


async def load_startup_extensions():
    await bot.wait_until_ready()
    total = len(startup_extensions)
    successes = 0
    for extension in startup_extensions:
        try:
            bot.load_extension(extension)
            print(f'Successfully loaded extension {extension}.')
            successes += 1
        except Exception as e:
            print(f'Failed to load extension {extension}.')
            traceback.print_exc()
            # ^uncomment for traceback when extension fails to load
    print('-' * 52)
    print(f'Successfully loaded {successes}/{total} extensions.')


@bot.event
async def on_ready():
    print(f'\nLogged in as: {bot.user.name} - {bot.user.id}\n'
          f'Python Version: {platform.python_version()}\n'
          f'Library Version: {discord.__version__}\n')

    activity = discord.Activity(type=discord.ActivityType.listening, name='you :)')
    await bot.change_presence(activity=activity)
    print(f'Ready! {datetime.datetime.now()}\n')
    await load_startup_extensions()


# @bot.check
# async def global_blacklist(ctx):
#     return ctx.author.id not in config.blacklist
if __name__ == "__main__":
    bot.run(TOKEN, reconnect=True)
