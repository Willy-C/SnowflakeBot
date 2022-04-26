import json
import traceback

import asyncpg

from bot import SnowflakeBot
from config import BOT_TOKEN, DBURI


async def create_db_pool() -> asyncpg.Pool:
    async def db_init(con):
        await con.set_type_codec('jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')

    return asyncpg.create_pool(DBURI, init=db_init)


async def run_bot() -> None:
    try:
        pool = await create_db_pool()
    except Exception:
        traceback.print_exc()
        print(f'\nUnable to connect to PostgreSQL, exiting...\n')
        return

    bot = SnowflakeBot()

    bot.pool = pool
    await bot.start(BOT_TOKEN)
