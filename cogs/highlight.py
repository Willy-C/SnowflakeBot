import discord
from discord.ext import commands

from typing import Union
from datetime import datetime, timezone, timedelta
from asyncio import TimeoutError


EDT_diff = timedelta(hours=-4)

class HighlightCog(commands.Cog, name='Highlight'):

    def __init__(self, bot):
        self.bot = bot
        self.highlights = {'willy': 94271181271605248}
        self.mentions = {94271181271605248}

        # maybe str -> [UserIDs] to support same keyword for multiple people

        # self.ignored_guilds = {} # UserID -> {Guild IDs} | int -> set(int)
        # self.ignored_channels = {} # UserID -> {Channel IDs} | int -> set(int)
        # self.ignored_users={} # UserID -> {User IDs} | int -> set(int)

    async def _get_msg_context(self, message: discord.Message, key: str, mention=False):
        prev_msgs = await message.channel.history(after=(datetime.utcnow()-timedelta(minutes=5))).flatten() # Grabs all messages from the last 5 minutes
        msg_context = []
        dateformat = '%m-%d %H:%M:%S'

        if not mention:
            if any([msg.author.id == self.highlights[key] for msg in prev_msgs[:-1]]): # If target recently spoke, no DM
                return # TODO: will have to redo this if decide to support multiple users for  1 keyword - make a list of users that need to be DM'ed

            if any([key.lower() in msg.content.lower() for msg in prev_msgs[:-1]]): # No need to spam highlights
                return

            for msg in prev_msgs[-4:-1]:
                msg_context.append(f'[{(msg.created_at + EDT_diff).strftime(dateformat)}] {msg.author}: {msg.content}')

            msg = prev_msgs[-1] # this is just so I can copy and paste the line above
            msg_context.append(f'[{(msg.created_at + EDT_diff).strftime(dateformat)}] {msg.author}: {msg.content.replace(key, f"**{key}**")}')

        else:
            for msg in prev_msgs[-4:]:
                msg_context.append(f'[{(msg.created_at + EDT_diff).strftime(dateformat)}] {msg.author}: {msg.content}')

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

        context = await self._get_msg_context(message, key)

        if context is None:  # target recently messaged, no need to DM
            return

        e = discord.Embed(title=f'You were mentioned in {message.guild} | #{message.channel}',
                          description=f'{context}\n'
                                      f'[Jump to message]({message.jump_url})',
                          color=discord.Color.blue())
        e.set_footer(text=f'Highlight word: {key}')
        target = self.bot.get_user(target_id)
        await target.send(embed=e)


    async def _dm_mention(self, message, id):
        context = await self._get_msg_context(message, '', True)

        e = discord.Embed(title=f'You were mentioned in {message.guild} | #{message.channel}',
                          description=f'{context}\n'
                                      f'[Jump to message]({message.jump_url})',
                          color=discord.Color.blue())

        target = self.bot.get_user(id)
        await target.send(embed=e)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        for key in self.highlights:
            if key in message.content.lower():
                await self._dm_highlight(message, key)

        for user in message.mentions:
            if user.id in self.mentions:
                await self._dm_mention(message, user.id)

    @commands.group(hidden=True)
    async def highlight(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @highlight.command()
    async def add(self, ctx, *, key):
        key = key.lower()
        if key in self.highlights:
            return await ctx.send('This key is already registered to someone. Sharing highlight keys is a feature in the future, sorry.')
        try:
            self.highlights[key] = ctx.author.id
        except:
            return await ctx.send('An error has occurred.')
        else:
            return await ctx.send(f'Successfully added highlight key: {key}')

    @highlight.command()
    async def remove(self, ctx, *, key):
        key = key.lower()
        if key not in self.highlights:
            return await ctx.send('Sorry, I cannot find this key')
        if self.highlights[key] != ctx.author.id:
            return await ctx.send('Sorry, you do not seem to own this key')
        try:
            self.highlights.pop(key)
        except:
            return await ctx.send('An error has occurred.')
        else:
            return await ctx.send(f'Successfully removed  highlight key: {key}')

    @highlight.command()
    async def list(self, ctx, *, user: Union[int, discord.User]=None):
        if isinstance(user,  discord.User):
            target = user.id
        else:
            target = user
            user = self.bot.get_user(user)
        if user is None:
            target = ctx.author.id
            user = ctx.author
        keys = '\n'.join([k for k,v in self.highlights.items() if v == target])
        e = discord.Embed(color=discord.Color.dark_orange(),
                          description=keys,
                          title='Highlight keys')
        e.set_author(name=user, icon_url=user.avatar_url)

        await ctx.send(embed=e)

    @highlight.command()
    async def mention(self, ctx):
        id = ctx.author.id
        if id in self.mentions:
            self.mentions.remove(id)
            await ctx.send('You will no longer get a DM when I see you mentioned', delete_after=10)
        else:
            self.mentions.add(id)
            await ctx.send('You will now get a DM when I see you mentioned', delete_after=10)

        await ctx.message.add_reaction('\U00002705')  # React with checkmark

def setup(bot):
    bot.add_cog(HighlightCog(bot))
