import discord
from discord.ext import commands

from typing import Union
from datetime import datetime, timezone, timedelta
from asyncio import TimeoutError

EDT_diff = timedelta(hours=-4)

class HighlightCog(commands.Cog, name='Highlight'):

    def __init__(self, bot):
        self.bot = bot
        self.highlights = {'willy': 94271181271605248} # maybe str -> [UserIDs] to support same keyword for multiple people
        # self.ignored_guilds = {} # UserID -> {Guild IDs} | int -> set(int)
        # self.ignored_channels = {} # UserID -> {Channel IDs} | int -> set(int)
        # self.ignored_users={} # UserID -> {User IDs} | int -> set(int)

    async def _get_msg_context(self, message: discord.Message, key: str):
        prev_msgs = await message.channel.history(after=(datetime.utcnow()-timedelta(minutes=5))).flatten() # Grabs all messages from the last 5 minutes
        msg_context = []
        dateformat = '%m-%d %H:%M:%S'

        if any([msg.author.id == self.highlights[key] for msg in prev_msgs[:-1]]): # If target recently spoke, no DM
            return # TODO: will have to redo this if decide to support multiple users for  1 keyword - make a list of users that need to be DM'ed

        if any([key.lower() in msg.content.lower() for msg in prev_msgs[:-1]]): # No need to spam highlights
            return

        for msg in prev_msgs[-4:-1]:
            msg_context.append(f'[{(msg.created_at + EDT_diff).strftime(dateformat)}] {msg.author}: {msg.content}')

        msg = prev_msgs[-1] # this is just so I can copy and paste the line above
        msg_context.append(f'[{(msg.created_at + EDT_diff).strftime(dateformat)}] {msg.author}: {msg.content.replace(key, f"**{key}**")}')

        for _ in range(2):  # Get next 2 messages within 10s
            try:
                next_msg = await self.bot.wait_for('message', check=(lambda m: m.channel == message.channel), timeout=5)
            except TimeoutError:
                pass
            else:
                msg_context.append(f'[{(next_msg.created_at + EDT_diff).strftime(dateformat)}] {next_msg.author}: {next_msg.content}')

        return '\n'.join(msg_context)

    async def _dm_highlight(self, message: discord.Message, key: str):

        target_id = self.highlights[key]

        if message.author.id == target_id:
            return
        # if target_id in self.ignored_guilds:
        #     if message.guild.id in self.ignored_guilds[target_id]:
        #         return
        # if target_id in self.ignored_channels:
        #     if message.channel.id in self.ignored_channels[target_id]:
        #         return
        # if target_id in self.ignored_users:
        #     if message.author.id in self.ignored_users[target_id]:
        #         return

        context = await self._get_msg_context(message, key)

        if context is None:  # target recently messaged, no need to DM
            return

        e = discord.Embed(title=f'You were mentioned in {message.guild} | #{message.channel}',
                          description=f'{context}\n'
                                      f'[Jump to message]({message.jump_url})',
                          color=discord.Color.blue())
        e.set_footer(text=f'Highlight word: {key.capitalize()}')
        target = self.bot.get_user(target_id)
        await target.send(embed=e)
        # await target.send(f'You were mentioned in {message.guild.name} | {message.channel}\n'
        #                   f'{context}\n'
        #                   f'Jump link: {message.jump_url}')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot:
            return

        for key in self.highlights:
            if key in message.content.lower():
                await self._dm_highlight(message, key)

    # @commands.group()
    # async def highlight(self, ctx):
    #     if ctx.invoked_subcommand is None:
    #         pass
    #
    # @highlight.command(enabled=False)
    # async def add(self, ctx):
    #     pass



def setup(bot):
    bot.add_cog(HighlightCog(bot))
