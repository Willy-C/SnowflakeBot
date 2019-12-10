import discord
from discord.ext import commands

import json
import aiohttp
import traceback, platform
from datetime import datetime

from config import BOT_TOKEN, blacklist

DESCR = 'This is a general purpose bot I am making for fun'

# File names of extensions we are loading on startup
startup_extensions = ['jishaku',
                      'cogs.error_handler',
                      'cogs.guild',
                      'cogs.owner',
                      'cogs.meta',
                      'cogs.avatar',
                      'cogs.logger',
                      'cogs.random',
                      'cogs.googleimage',
                      'cogs.general',
                      'cogs.highlight',
                      'cogs.mod',
                      'cogs.prefix',
                      'cogs.latex',
                      'cogs.info',
                      'cogs.wavelink',
                      'cogs.wash',
                      'cogs.vi',
                      'cogs.gatekeep',
                      'cogs.reddit']


def get_prefix(bot, message):
    """A callable prefix for our bot. Returns a list of valid prefixes for the guild"""
    bot_id = bot.user.id
    prefixes = [f'<@{bot_id}> ', f'<@!{bot_id}> ']  # Accept mentioning the bot as prefix
    if message.guild is None:
        prefixes.append('%')
    else:
        prefixes.extend(bot.prefixes.get(message.guild.id, '%'))
    return prefixes


class SnowflakeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, description=DESCR, case_insensitive=True,
                         activity=discord.Activity(type=discord.ActivityType.listening, name='you :)'))

        self.starttime = datetime.utcnow()
        self.blacklist = blacklist
        self.session = aiohttp.ClientSession(loop=self.loop)

        with open('data/prefixes.json') as f:
            self.prefixes = {int(k): v for k, v in json.load(f).items()}

    async def close(self):
        await super().close()
        await self.session.close()


bot = SnowflakeBot()


@bot.event
async def on_ready():
    print(f'\nLogged in as: {bot.user.name} - {bot.user.id}\n'
          f'Python Version: {platform.python_version()}\n'
          f'Library Version: {discord.__version__}\n')

    print(f'Ready! {datetime.now()}\n')


if __name__ == '__main__':
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

    print('-' * 52)
    print(f'Successfully loaded {successes}/{total} extensions.')

bot.run(BOT_TOKEN, reconnect=True)
