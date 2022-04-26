from __future__ import annotations

import platform
import pathlib
import asyncio
from typing import Union, List
from datetime import datetime

import aiohttp
import asyncpg
import discord
from discord.ext import commands

from utils.context import Context


DESCRIPTION = 'This is a general purpose bot I am making for fun.'


def get_prefix(bot: SnowflakeBot, message: discord.Message) -> List[str]:
    """A callable prefix for our bot. Returns a list of valid prefixes for the guild"""
    bot_id = bot.user.id
    prefixes = [f'<@{bot_id}> ', f'<@!{bot_id}> ']  # Accept mentioning the bot as prefix
    if message.guild is None:
        prefixes.append('%')
        # prefixes.append('')  # Also accept no prefix in DMs
    else:
        prefixes.extend(bot.prefixes.get(message.guild.id, '%'))
    return prefixes


class SnowflakeBot(commands.Bot):
    user: discord.ClientUser
    pool: asyncpg.Pool
    prefixes: dict[int, List[str]]
    session: aiohttp.ClientSession

    def __init__(self) -> None:
        super().__init__(command_prefix=get_prefix,
                         description=DESCRIPTION,
                         case_insensitive=True,
                         activity=discord.Activity(type=discord.ActivityType.listening, name='you :)'),
                         help_command=commands.MinimalHelpCommand(),
                         allowed_mentions=discord.AllowedMentions(everyone=False),
                         intents=discord.Intents.all())

        self.starttime = datetime.utcnow()

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.prefixes = await self.fetch_prefixes()

        # This is might not be filled if bot.is_owner has not been called so we will fill it manually
        app_info = await self.application_info()
        self.owner_id: int = app_info.owner.id

        await self.load_extension('jishaku')
        count = 1

        # Thanks Umbra and Maya!
        for file in pathlib.Path('cogs').glob('[!_]*.py'):
            ext = ".".join(file.parts).removesuffix('.py')
            await self.load_extension(ext)
            count += 1
        print(f'Loaded {count} extensions')

    @property
    def owner(self) -> discord.User:
        return self.get_user(self.owner_id)

    async def fetch_prefixes(self) -> dict[int, List[str]]:
        query = '''SELECT * 
                   FROM prefixes
                   ORDER BY CASE WHEN prefix = '%' THEN 0 ELSE 1 END;'''
        records = await self.pool.fetch(query)

        collect_prefixes = {}
        for record in records:
            gid = record['guild']
            if gid in collect_prefixes:
                collect_prefixes[gid].append(record['prefix'])
            else:
                collect_prefixes[gid] = [record['prefix']]
        return {g: p for g, p in collect_prefixes.items()}

    async def on_ready(self) -> None:
        print(f'Ready! {self.user} - {self.user.id}'
              f'Python Version: {platform.python_version()}\n'
              f'Library Version: {discord.__version__}\n'
              f'Time: {datetime.utcnow()}')

    async def get_context(self, origin: Union[discord.Message, discord.Interaction], /, *, cls=Context) -> Context:
        return await super().get_context(origin, cls=cls)

    async def close(self) -> None:
        await self.session.close()
        await super().close()
        await asyncio.wait_for(self.pool.close(), timeout=20)
