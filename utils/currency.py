import discord
from discord.ext import commands


async def increase_balance(ctx, user: discord.User, amount: float):
    query = '''INSERT INTO currency(id, money)
               VALUES($1, $2) ON CONFLICT (id) DO UPDATE
               SET money = currency.money + $2'''
    await ctx.bot.pool.execute(query, user.id, round(amount, 2))


async def decrease_balance(ctx, user: discord.User, amount: float):
    await increase_balance(ctx, user, -amount)


async def set_balance(ctx, user: discord.User, amount: float):
    query = '''INSERT INTO currency(id, money)
               VALUES($1, $2) ON CONFLICT (id) DO UPDATE
               SET money = $2'''
    await ctx.bot.pool.execute(query, user.id, round(amount, 2))


async def get_balance(ctx, user: discord.User) -> float:
    query = '''SELECT money FROM currency WHERE id = $1'''
    record = await ctx.bot.pool.fetchrow(query, user.id)
    if record is None:
        return 0
    else:
        return float(record['money'])


async def has_balance(ctx, user: discord.User, amount: float):
    balance = await get_balance(ctx, user)
    return balance >= amount
