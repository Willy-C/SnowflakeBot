from __future__ import annotations

import json
import traceback
import platform
import pathlib
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from typing import Union, List, Optional
from datetime import datetime

import mystbin
import aiohttp
import asyncpg
import discord
from discord.ext import commands

from utils.context import Context
from config import BOT_TOKEN, DBURI


try:
    import uvloop
    uvloop.install()
    print('Using uvloop')
except ImportError:
    print('uvloop not installed')

log = logging.getLogger(__name__)


class RemoveNoise(logging.Filter):
    def __init__(self):
        super().__init__(name='discord.state')

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelname == 'WARNING' and 'referencing an unknown' in record.msg:
            return False
        return True


class LogHandler:
    def __init__(self, *, stream: bool = True) -> None:
        self.log: logging.Logger = logging.getLogger()
        self.max_bytes: int = 32 * 1024 * 1024  # 32 MiB
        self.logging_path = pathlib.Path('./logs/')
        self.logging_path.mkdir(exist_ok=True)
        self.stream: bool = stream

    async def __aenter__(self):
        return self.__enter__()

    def __enter__(self):
        discord.utils.setup_logging()
        logging.getLogger('discord').setLevel(logging.INFO)
        logging.getLogger('discord.http').setLevel(logging.INFO)
        logging.getLogger('discord.ext.tasks').setLevel(logging.INFO)
        logging.getLogger('discord.state').addFilter(RemoveNoise())

        self.log.setLevel(logging.INFO)
        handler = RotatingFileHandler(
            filename=self.logging_path / "snowflake.log",
            encoding='utf-8',
            mode='w',
            maxBytes=self.max_bytes,
            backupCount=5,
        )
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        fmt = logging.Formatter('[{asctime}] [{levelname:<7}] {name}: {message}', dt_fmt, style='{')
        handler.setFormatter(fmt)
        self.log.addHandler(handler)

        return self

    async def __aexit__(self, *args) -> None:
        return self.__exit__(*args)

    def __exit__(self, *args) -> None:
        handlers = self.log.handlers[:]
        for hdlr in handlers:
            hdlr.close()
            self.log.removeHandler(hdlr)


DESCRIPTION = 'This is a general purpose bot I am making for fun.'


async def create_db_pool() -> asyncpg.Pool:
    async def db_init(con):
        await con.set_type_codec('jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')

    return asyncpg.create_pool(DBURI, init=db_init, command_timeout=60)


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
    mb_client: mystbin.Client

    def __init__(self) -> None:
        super().__init__(command_prefix=get_prefix,
                         description=DESCRIPTION,
                         case_insensitive=True,
                         activity=discord.Activity(type=discord.ActivityType.listening, name='you :)'),
                         help_command=commands.MinimalHelpCommand(),
                         allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
                         intents=discord.Intents.all())

        self.starttime = datetime.utcnow()

    async def setup_hook(self) -> None:
        self.prefixes = await self.fetch_prefixes()

        # This is might not be filled if bot.is_owner has not been called so we will fill it manually
        app_info = await self.application_info()
        self.owner_id = app_info.owner.id

    @property
    def owner(self) -> discord.User | None:
        return self.get_user(self.owner_id)

    @property
    def config(self):
        return __import__('config')

    async def fetch_prefixes(self) -> dict[int, List[str]]:
        query = '''SELECT * FROM prefixes;'''
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
        print(f'Ready! {self.user} - {self.user.id}\n'
              f'Python Version: {platform.python_version()}\n'
              f'Library Version: {discord.__version__}\n'
              f'Time: {discord.utils.utcnow()}')
        log.info('Ready! %s - %s', self.user, self.user.id)

    async def get_context(self, origin: Union[discord.Message, discord.Interaction], /, *, cls=Context) -> Context:
        return await super().get_context(origin, cls=cls)

    async def get_or_fetch_user(self, member_id: int) -> Optional[discord.User]:
        try:
            return self.get_user(member_id) or (await self.fetch_user(member_id))
        except discord.HTTPException:
            return None

    async def close(self) -> None:
        await self.session.close()
        await super().close()


async def main() -> None:
    try:
        pool = await create_db_pool()
    except Exception:
        traceback.print_exc()
        print(f'\nUnable to connect to PostgreSQL, exiting...\n')
        raise

    async with pool, SnowflakeBot() as bot, aiohttp.ClientSession() as session, LogHandler():
        bot.pool = pool
        bot.session = session
        bot.mb_client = mystbin.Client(session=session)

        await bot.load_extension('jishaku')
        count = 1

        # Autoload all cogs in the cogs folder except for those that start with an underscore
        for file in pathlib.Path('cogs').glob('**/[!_]*.py'):
            ext = ".".join(file.parts).removesuffix('.py')
            try:
                await bot.load_extension(ext)
            except commands.ExtensionFailed as e:
                raise e.original
            count += 1
        print(f'Loaded {count} extensions')

        await bot.start(BOT_TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
