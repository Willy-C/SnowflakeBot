import discord
from discord.ext import commands

from typing import Union
from datetime import datetime, timezone


class HighlightCog(commands.Cog, name='Highlight'):

    def __init__(self, bot):
        self.bot = bot
        self.highlights = {'willy': 94271181271605248}
        self.keys = self.highlights.keys()

    async def _get_msg_context(self, message: discord.Message, key: str):
        prev_msg = await message.channel.history(limit=5, before=message).flatten() # Grabs the previous 5 messages
        formatted = []
        dateformat = '%m-%d %H:%M:%S'
        for msg in prev_msg:
            if (datetime.utcnow()-msg.created_at).total_seconds() < 900: # Only care about messages within last 15 minutes
                if msg.author.id == self.highlights[key]: # If target recently spoke, no DM
                    return
                if key.lower() in msg.content.lower(): # No need to spam mentions
                    return
                formatted.append(f'[{msg.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime(dateformat)}] {msg.author}: {msg.content}')

        formatted.reverse()
        formatted.append( f'[{message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime(dateformat)}] {message.author}: {message.content}')
        return '\n'.join(formatted)

    async def _dm_highlight(self, message: discord.Message, key: str):
        target = self.bot.get_user(self.highlights[key])
        if message.author == target:
            return
        context = await self._get_msg_context(message, key)

        if context is None: # target recently messaged, no need to DM
            return

        e = discord.Embed(title=f'You were mentioned in {message.guild.name} | #{message.channel}',
                          description=f'{context}\n'
                                      f'[Jump to message]({message.jump_url})',
                          color=discord.Color.blue())
        await target.send(embed=e)
        # await target.send(f'You were mentioned in {message.guild.name} | {message.channel}\n'
        #                   f'{context}\n'
        #                   f'Jump link: {message.jump_url}')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.id == self.bot.user.id:
            return

        for key in self.keys:
            if key.lower() in message.content.lower():
                await self._dm_highlight(message, key)


def setup(bot):
    bot.add_cog(HighlightCog(bot))
