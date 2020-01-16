import discord
from discord.ext import commands

import aiohttp

from config import DEEPAI_API_KEY

API_URL = 'https://api.deepai.org/api/waifu2x'
HEADERS = {'api-key': DEEPAI_API_KEY}


class LastImage(commands.Converter):
    """Converter that tries to find the last image in chat.
    Raises BadArgument if no image found within limit."""
    async def convert(self, ctx, argument):
        async for message in ctx.channel.history(limit=25):
            for embed in message.embeds:
                if embed.thumbnail and embed.thumbnail.proxy_url:
                    return embed.thumbnail.proxy_url
            for attachment in message.attachments:
                if attachment.proxy_url:
                    return attachment.proxy_url
        raise commands.BadArgument


class Waifu2x(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_image(self, url):
        image_formats = ('image/png', 'image/jpeg', 'image/jpg')
        try:
            async with self.bot.session.head(url) as resp:
                return resp.headers['Content-Type'] in image_formats
        except (aiohttp.InvalidURL, KeyError):
            return False

    @commands.command(hidden=True)
    async def upscale(self, ctx, url=None):
        url = url or await LastImage().convert(ctx, url)
        if not await self.is_image(url):
            return await ctx.send('That is not a valid image url')
        data = {
            'image': url
        }
        async with self.bot.session.post(API_URL, data=data, headers=HEADERS) as resp:
            jdata = await resp.json()
            await ctx.send(jdata.get('output_url', 'Failed'))


def setup(bot):
    bot.add_cog(Waifu2x(bot))
