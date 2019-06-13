import discord
from discord.ext import commands

from typing import Union
from datetime import datetime, timezone, timedelta

EDT_diff = timedelta(hours=-4)

class HighlightCog(commands.Cog, name='Highlight'):

    def __init__(self, bot):
        self.bot = bot
        self.highlights = {'willy': 94271181271605248}
        self.keys = self.highlights.keys()

    async def _get_msg_context(self, message: discord.Message, key: str):
        prev_msgs = await message.channel.history(after=(datetime.utcnow()-timedelta(minutes=15))).flatten() # Grabs all messages from the last 15 minutes
        formatted = []
        dateformat = '%m-%d %H:%M:%S'

        if any([msg.author.id == self.highlights[key] for msg in prev_msgs[:-1]]): # If target recently spoke, no DM
            return

        if any([key.lower() in msg.content.lower() for msg in prev_msgs[:-1]]): # No need to spam highlights
            return

        for msg in prev_msgs[-6:]:
            formatted.append(f'[{(msg.created_at + EDT_diff).strftime(dateformat)}] {msg.author}: {msg.content}')

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
