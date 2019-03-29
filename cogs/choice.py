import discord
from discord.ext import commands

import random


class ChoiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='choice')
    async def random_choice(self, ctx, *choices: commands.clean_content):
        if len(choices) < 2:
            return await ctx.send('Need more choices to choose from!')

        await ctx.send(random.choice(choices))


def setup(bot):
    bot.add_cog(ChoiceCog(bot))
