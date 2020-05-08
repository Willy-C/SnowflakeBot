import discord
import asyncpg
from discord.ext import commands

import aiohttp
import asyncio
import traceback
import platform
from datetime import datetime
from sys import exit

from config import BOT_TOKEN, DBURI

DESCR = 'This is a general purpose bot I am making for fun'

# File names of extensions we are loading on startup
startup_extensions = ['jishaku',
                      'cogs.error_handler',
                      'cogs.guild',
                      'cogs.owner',
                      'cogs.meta',
                      'cogs.logger',
                      'cogs.random',
                      'cogs.general',
                      'cogs.highlight',
                      'cogs.mod',
                      'cogs.prefix',
                      'cogs.latex',
                      'cogs.info',
                      'cogs.wavelink',
                      'cogs.wash',
                      # 'cogs.vi',
                      'cogs.gatekeep',
                      'cogs.reddit',
                      'cogs.emoji',
                      'cogs.waifu2x',
                      'cogs.help',
                      'cogs.reminder',
                      'cogs.timezone',
                      'cogs.tracker',
                      'cogs.guild_config',
                      'cogs.avatars']


def get_prefix(bot, message):
    """A callable prefix for our bot. Returns a list of valid prefixes for the guild"""
    bot_id = bot.user.id
    prefixes = [f'<@{bot_id}> ', f'<@!{bot_id}> ']  # Accept mentioning the bot as prefix
    if message.guild is None:
        prefixes.append('%')
    else:
        prefixes.extend(bot.prefixes.get(message.guild.id, '%'))
    return prefixes


async def set_prefixes(bot):
    query = '''SELECT * 
               FROM prefixes
               ORDER BY CASE WHEN prefix = '%' THEN 0 ELSE 1 END;'''
    records = await bot.pool.fetch(query)

    collect_prefixes = {}
    for record in records:
        gid = record['guild']
        if gid in collect_prefixes:
            collect_prefixes[gid].append(record['prefix'])
        else:
            collect_prefixes[gid] = [record['prefix']]
    bot.prefixes = {g: p for g, p in collect_prefixes.items()}


class SnowflakeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix,
                         description=DESCR,
                         case_insensitive=True,
                         activity=discord.Activity(type=discord.ActivityType.listening, name='you :)'),
                         help_command=commands.MinimalHelpCommand())

        self.starttime = datetime.utcnow()
        self.session = aiohttp.ClientSession(loop=self.loop)

        self.loop.create_task(set_prefixes(self))

    async def close(self):
        await self.session.close()
        await super().close()
        await asyncio.wait_for(self.pool.close(), timeout=20)


loop = asyncio.get_event_loop()
try:
    pool = loop.run_until_complete(asyncpg.create_pool(DBURI))
except Exception:
    print(f'\nUnable to connect to PostgreSQL, exiting...\n')
    traceback.print_exc()
    exit()
else:
    print('\nConnected to PostgreSQL\n')

bot = SnowflakeBot()
bot.pool = pool


@bot.event
async def on_ready():
    print(f'\nLogged in as: {bot.user.name} - {bot.user.id}\n'
          f'Python Version: {platform.python_version()}\n'
          f'Library Version: {discord.__version__}\n')

    print(f'Ready! {datetime.utcnow()}\n')


total = len(startup_extensions)
successes = 0
for extension in startup_extensions:
    try:
        bot.load_extension(extension)
        print(f'Successfully loaded extension {extension}.')
        successes += 1
    except Exception:
        print(f'Failed to load extension {extension}.')
        traceback.print_exc()

print('-' * 52)
print(f'Successfully loaded {successes}/{total} extensions.')


bot.run(BOT_TOKEN)
