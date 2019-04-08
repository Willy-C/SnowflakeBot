import discord
from discord.ext import commands

import unicodedata


class CharCog(commands.Cog, name='General'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def charinfo(self, ctx, *, characters: str):
        """Gives you information about character(s).
        Only up to 25 characters at a time.
        """

        def to_string(c):
            digit = f'{ord(c):x}'
            name = unicodedata.name(c, 'Name not found.')
            return f'`\\U{digit:>08}`: {name} - {c} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>'

        msg = '\n'.join(map(to_string, characters))
        if len(msg) > 2000:
            return await ctx.send('Output too long to display.')
        await ctx.send(msg)


def setup(bot):
    bot.add_cog(CharCog(bot))
