import discord
from discord.ext import commands
import random

from typing import Optional


class RollCog(commands.Cog, name='General Commands'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='roll')
    async def roll_die(self, ctx, num_die: Optional[int] = 1, faces: Optional[int] = 6, sorted: bool = False):
        rolls = []
        for _ in range(num_die):
            rolls.append(random.randint(1, faces))
        sort = ''
        if sorted:
            rolls.sort()
            sort = 'Sorted '  # Empty string if unsorted

        separator = ' '  # Space between each element in list when outputting

        embed = discord.Embed(colour=discord.Color.dark_teal(),
                              description=f'{sort}Results for rolling a {faces} sided die {num_die} time(s):')
        embed.add_field(name='Rolls', value=separator.join(str(roll) for roll in rolls))
        embed.add_field(name='Total', value=sum(rolls), inline=False)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(RollCog(bot))
