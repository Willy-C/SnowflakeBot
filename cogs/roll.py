import discord
from discord.ext import commands
import random


class RollCog(commands.Cog, name='General Commands'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='roll')
    async def roll_die(self, ctx, num_die: int = 1, faces: int = 6):
        rolls = []
        for _ in range(num_die):
            rolls.append(random.randint(1, faces))
            separator = ' '

        embed = discord.Embed(colour=discord.Color.dark_teal(),
                              description=f'Results for rolling {faces} sided die {num_die} time(s):')
        embed.add_field(name='Rolls', value=separator.join(str(roll) for roll in rolls))
        embed.add_field(name='Total', value=sum(rolls))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(RollCog(bot))
