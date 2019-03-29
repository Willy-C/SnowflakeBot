import discord
from discord.ext import commands
import random

from typing import Optional


class RNGCog(commands.Cog, name='RNG Commands'):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def random(self, ctx):
        if ctx.invoked_subcommand is None:
            raise commands.MissingRequiredArgument

    @random.command(name='number', aliases=['num'])
    async def random_num(self, ctx, min: int = 0, max: int = 10):
        if max <= min:
            max, min = min, max
        await ctx.send(random.randint(min, max))

    @commands.command(name='roll')
    async def roll_die(self, ctx, num_rolls: Optional[int] = 1, faces: Optional[int] = 6, sorted: bool = False):
        rolls = []
        for _ in range(num_rolls):
            rolls.append(random.randint(1, faces))
        sort = ''
        if sorted:
            rolls.sort()
            sort = 'Sorted '  # Empty string if unsorted

        separator = ' '  # Space between each element in list when outputting

        embed = discord.Embed(colour=discord.Color.dark_teal(),
                              description=f'{sort}Results for rolling a {faces} sided die {num_rolls} time(s):')
        embed.add_field(name='Rolls', value=separator.join(str(roll) for roll in rolls))
        embed.add_field(name='Total', value=sum(rolls), inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='choice')
    async def random_choice(self, ctx, *choices: commands.clean_content):
        if len(choices) < 2:
            return await ctx.send('Need more choices to choose from!')

        await ctx.send(random.choice(choices))


def setup(bot):
    bot.add_cog(RNGCog(bot))
