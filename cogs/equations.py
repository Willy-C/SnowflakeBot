import io
from datetime import datetime

import discord
from discord.ext import commands

from utils.context import Context
from utils.global_utils import bright_color
from config import WOLFRAM_ALPHA_APPID

WOLFRAM_API = 'http://api.wolframalpha.com/v1/simple'


class MathCog(commands.Cog, name='Math'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='wolframalpha', aliases=['wolfram', 'wa', 'math', 'solve'])
    async def wolframalpha(self, ctx: Context, *, query: str):
        wolfram_payload = {
            'appid': WOLFRAM_ALPHA_APPID,
            'i': query,
            'layout': 'labelbar',
            'background': 'black',
            'foreground': 'white',
            'width': '800',
            'fontsize': '22',
            'units': 'metric',
        }
        async with ctx.typing():
            async with self.bot.session.get(WOLFRAM_API, params=wolfram_payload) as resp:
                # https://products.wolframalpha.com/simple-api/documentation
                if resp.status in (400, 501):
                    return await ctx.reply('Invalid query')
                data = io.BytesIO(await resp.read())

        e = discord.Embed(color=bright_color(), timestamp=datetime.utcnow())
        e.set_image(url='attachment://response.png')
        e.set_footer(text=f'Query: {query[:30] + "..." if len(query)>30 else query}')
        await ctx.reply(embed=e, file=discord.File(data, filename='response.png'), mention_author=False)
        await ctx.tick()


def setup(bot):
    bot.add_cog(MathCog(bot))
