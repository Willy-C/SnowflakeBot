import discord
from discord.ext import commands, tasks

import json
from datetime import datetime, timedelta
from asyncio import TimeoutError


EDT_diff = timedelta(hours=-4)


class HighlightCog(commands.Cog, name='Highlight'):

    def __init__(self, bot):
        self.bot = bot
        with open('data/highlights.json') as f:
            self.highlights = json.load(f)
        with open('data/mentions.json') as f:
            self.mentions = set(json.load(f))
        self.save_to_json.start()

        # maybe str -> [UserIDs] to support same keyword for multiple people

        # self.ignored_guilds = {} # UserID -> {Guild IDs} | int -> set(int)
        # self.ignored_channels = {} # UserID -> {Channel IDs} | int -> set(int)
        # self.ignored_users={} # UserID -> {User IDs} | int -> set(int)

    def save_highlights(self):
        with open('data/highlights.json', 'w') as f:
            json.dump(self.highlights, f, indent=2)

    def save_mentions(self):
        with open('data/mentions.json', 'w') as f:
            json.dump(list(self.mentions), f, indent=2)

    async def _get_msg_context(self, message: discord.Message, key: str, mention=False):
        prev_msgs = await message.channel.history(after=(datetime.utcnow()-timedelta(minutes=5))).flatten()  # Grabs all messages from the last 5 minutes
        msg_context = []
        dateformat = '%m-%d %H:%M:%S'

        if not mention:
            if any([msg.author.id == self.highlights[key] for msg in prev_msgs[:-1]]):  # If target recently spoke, no DM
                return  # TODO: will have to redo this if decide to support multiple users for  1 keyword - make a list of users that need to be DM'ed

            if any([key.lower() in msg.content.lower() for msg in prev_msgs[:-1]]):  # No need to spam highlights
                return

            for msg in prev_msgs[-4:-1]:
                msg_context.append(f'[{(msg.created_at + EDT_diff).strftime(dateformat)}] {msg.author}: {msg.content}')

            msg = prev_msgs[-1]  # this is just so I can copy and paste the line above
            msg_context.append(f'[{(msg.created_at + EDT_diff).strftime(dateformat)}] {msg.author}: {msg.content.replace(key, f"**{key}**")}')

        else:
            if any([user.id == key for msg in prev_msgs[:-1] for user in msg.mentions]):
                return

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

        member = message.guild.get_member(target_id)
        if (member is None or not member.permissions_in(message.channel).read_messages) and target_id != self.bot.owner_id:
            return

        context = await self._get_msg_context(message, key)

        if context is None:  # target recently messaged, no need to DM
            return

        e = discord.Embed(title=f'You were mentioned in {message.guild} | #{message.channel}',
                          description=f'{context}\n'
                                      f'[Jump to message]({message.jump_url})',
                          color=discord.Color(0x00B0F4))
        e.set_footer(text=f'Highlight word: {key}')
        target = self.bot.get_user(target_id)
        await target.send(embed=e)

    async def _dm_mention(self, message, _id):
        context = await self._get_msg_context(message, _id, True)

        if context is None:  # target recently messaged, no need to DM
            return

        e = discord.Embed(title=f'You were mentioned in {message.guild} | #{message.channel}',
                          description=f'{context}\n'
                                      f'[Jump to message]({message.jump_url})',
                          color=discord.Color(0xFAA61A))

        target = self.bot.get_user(_id)
        await target.send(embed=e)
        await message.add_reaction('\U0001f440')  # eyes

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

    @commands.group()
    async def highlight(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @highlight.command()
    async def add(self, ctx, *, key):
        """Add a highlight keyword"""
        key = key.lower()
        if key in self.highlights:
            return await ctx.send('This key is already registered to someone. Sharing highlight keys currently not supported but is planned, sorry.')
        try:
            self.highlights[key] = ctx.author.id
        except:
            return await ctx.send('An error has occurred.')
        else:
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
            return await ctx.send(f'Successfully added highlight key: {key}', delete_after=10)


    @highlight.command()
    async def remove(self, ctx, *, key):
        """Remove a highlight keyword"""
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
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
            return await ctx.send(f'Successfully removed  highlight key: {key}', delete_after=10)

    @highlight.command()
    async def list(self, ctx):
        """Lists your highlight keywords"""
        target = ctx.author.id
        user = ctx.author

        keys = '\n'.join([k for k, v in self.highlights.items() if v == target])
        if keys:
            e = discord.Embed(color=discord.Color.dark_orange(),
                              description=keys,
                              title='Highlight keys')
        else:
            e = discord.Embed(color=discord.Color.dark_orange(),
                              description='You do not have any highlight keys')
        e.add_field(name='Mentions', value=target in self.mentions)
        e.set_author(name=user, icon_url=user.avatar_url)

        await ctx.message.add_reaction('\U00002705')  # React with checkmark
        await ctx.send(embed=e, delete_after=15)

    @highlight.command()
    async def mention(self, ctx):
        """Toggle highlight for mentions"""
        if ctx.author.id in self.mentions:
            self.mentions.remove(ctx.author.id)
            await ctx.send('You will no longer get a DM when I see you mentioned', delete_after=10)
            await ctx.message.add_reaction('\U00002796')  # React with heavy plus sign
        else:
            self.mentions.add(ctx.author.id)
            await ctx.send('You will now get a DM when I see you mentioned', delete_after=10)
            await ctx.message.add_reaction('\U00002795')  # React with heavy minus sign

    @highlight.command()
    @commands.is_owner()
    async def save(self, ctx):
        try:
            self.save_highlights()
            self.save_mentions()
        except:
            await ctx.send('An error has occurred ')
        else:
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

    # noinspection PyCallingNonCallable
    @tasks.loop(hours=6)
    async def save_to_json(self):
        self.save_highlights()
        self.save_mentions()

    def cog_unload(self):
        self.save_to_json.cancel()
        self.save_highlights()
        self.save_mentions()


def setup(bot):
    bot.add_cog(HighlightCog(bot))
