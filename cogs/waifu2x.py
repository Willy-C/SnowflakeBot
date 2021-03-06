import discord
from discord.ext import commands

from utils.global_utils import bright_color, last_image, is_image
from config import DEEPAI_API_KEY

API_URL = 'https://api.deepai.org/api/waifu2x'
HEADERS = {'api-key': DEEPAI_API_KEY}


class Waifu2x(commands.Cog, command_attrs={'hidden': True}):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def upscale(self, ctx, url=None):
        url = url or await last_image(ctx)
        if url is None:
            return await ctx.send('Unable to find an image')
        if not await is_image(ctx, url):
            return await ctx.send('That is not a valid image url')
        data = {
            'image': url
        }
        async with self.bot.session.post(API_URL, data=data, headers=HEADERS) as resp:
            jdata = await resp.json()
            img_url = jdata.get('output_url')
        if img_url is None:
            return await ctx.send('Failed')
        e = discord.Embed(colour=bright_color())
        e.set_image(url=img_url)
        e.set_author(name='Upscale', url=img_url)
        await ctx.send(embed=e)

    @commands.command()
    async def lastimage(self, ctx):
        url = await last_image(ctx)
        if url is None:
            return await ctx.send('Unable to find an image')
        e = discord.Embed(colour=bright_color())
        e.set_image(url=url)
        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(Waifu2x(bot))
