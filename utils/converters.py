import discord
from discord.ext import commands

class LastImage(commands.Converter):
    """Converter that tries to find the last image in chat.
    Raises BadArgument if no image found within limit."""
    async def convert(self, ctx, argument):
        async for message in ctx.channel.history(limit=50):
            for embed in message.embeds:
                if embed.thumbnail and embed.thumbnail.proxy_url:
                    return embed.thumbnail.proxy_url
            for attachment in message.attachments:
                if attachment.proxy_url:
                    return attachment.proxy_url
        raise commands.BadArgument
