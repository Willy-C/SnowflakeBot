import discord
from discord.ext import commands

import time


class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='Gets the ping')
    async def ping(self, ctx):
        start = time.perf_counter()
        message = await ctx.send('Beep...')
        end = time.perf_counter()
        duration = (end - start) * 1000

        await message.edit(content=f'Boop\n'
                                   f'Ping:{duration:.2f}ms')


def setup(bot):
    bot.add_cog(Ping(bot))
