import discord
from discord.ext import commands

import sys, traceback, platform
from typing import Union
import datetime

import config

DESCR = 'This bot is a small side project and still very WIP'
TOKEN = config.BOT_TOKEN

# File names of extensions we are loading on startup
startup_extensions = ['jishaku',
                      'cogs.error_handler',
                      'cogs.members',
                      'cogs.owner',
                      'cogs.metautil',
                      'cogs.avatar',
                      'cogs.logger',
                      'cogs.random',
                      'cogs.googleimage',
                      'cogs.charinfo',
                      'cogs.fun']

def get_prefix(bot, message):
    """A callable Prefix for our bot. This could be edited to allow per server prefixes."""

    prefixes = ['?', '!', '%']

    # Check to see if we are outside of a guild. e.g DM's etc.
    if not message.guild:
        # Only allow ? to be used in DMs
        return '?'

    # If in a guild, allow for the user to mention or use any of the prefixes in the list.
    return commands.when_mentioned_or(*prefixes)(bot, message)


bot = commands.Bot(command_prefix=get_prefix, description=DESCR)


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
    print('----------------------------------------------------')
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

bot.run(TOKEN, reconnect=True)
