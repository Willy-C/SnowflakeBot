import discord
from discord.ext import commands


class PingCog(commands.Cog, name='Utility'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief='Gets the ping')
    async def ping(self, ctx):
        ping = round(self.bot.latency * 1000)
        await ctx.send(f"Ping: `{ping}ms`")


def setup(bot):
    bot.add_cog(PingCog(bot))
