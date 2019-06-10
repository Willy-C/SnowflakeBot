import discord
from discord.ext import commands

from typing import Union
from datetime import datetime, timezone


class HighlightCog(commands.Cog, name='Highlight'):

    def __init__(self, bot):
        self.bot = bot
        self.highlights = {'willy': 94271181271605248}
        self.keys = self.highlights.keys()

    async def _get_msg_context(self, message: discord.Message):
        prev_msg = await message.channel.history(limit=5, before=message).flatten()
        formatted = []
        dateformat = '%m-%d %H:%M:%S'
        for msg in prev_msg:
            formatted.append(
                f'[{msg.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime(dateformat)}] {msg.content}')
        formatted.reverse()
        formatted.append(
            f'[{message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime(dateformat)}] {message.content}')
        return '\n'.join(formatted)

    async def _dm_highlight(self, message: discord.Message, key: str):

        target = self.bot.get_user(self.highlights[key])
        if message.author == target:
            return
        context = await self._get_msg_context(message)
        # await target.send(f'You were mentioned in {discord.utils.escape_markdown(message.guild.name)} | {discord.utils.escape_markdown(message.channel.name)}\n'
        await target.send(f'You were mentioned in {message.guild.name} | {message.channel}\n'
                          f'{context}\n'
                          f'Jump link: {message.jump_url}')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.id == self.bot.user.id:
            return

        for key in self.keys:
            if key.lower() in message.content.lower():
                await self._dm_highlight(message, key)


def setup(bot):
    bot.add_cog(HighlightCog(bot))
