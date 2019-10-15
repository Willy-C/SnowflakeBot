import discord
from discord.ext import commands, tasks

import json
import re
from datetime import datetime, timedelta
from asyncio import TimeoutError
from typing import Union


class HighlightCog(commands.Cog, name='Highlight'):

    def __init__(self, bot):
        self.bot = bot
        with open('data/highlights.json') as f:
            self.highlights = json.load(f)
        with open('data/mentions.json') as f:
            self.mentions = set(json.load(f))
        with open('data/highlightignores.json') as f:
            self.ignores = {int(k): v for k, v in json.load(f).items()}
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

    def save_ignores(self):
        with open('data/highlightignores.json', 'w') as f:
            json.dump(self.ignores, f, indent=2)

    def ignore_check(self, message: discord.Message, _id: int):
        ignore = self.ignores.get(_id)
        if ignore:
            if message.guild.id in ignore.get('guilds', []):
                return False
            if message.channel.id in ignore.get('channels', []):
                return False
            if message.author.id in ignore.get('users', []):
                return False
        return True

    async def _get_msg_context(self, message: discord.Message, key: str, mention=False):

        prev_msgs = await message.channel.history(after=(datetime.utcnow()-timedelta(minutes=5))).flatten()  # Grabs all messages from the last 5 minutes
        msg_context = []
        now = datetime.utcnow()

        for msg in prev_msgs[-4:-1]:
            msg_context.append(f'`[-{str(abs(now-msg.created_at)).split(".")[0][3:]}]` {msg.author}: {msg.content}')

        msg = prev_msgs[-1]
        bolded = re.sub(f'({key})', r'**\1**', msg.content, flags=re.IGNORECASE) # f-string expression part cannot include a backslash
        if not mention:
            msg_context.append(f'**`[-----]`** {msg.author}: {bolded}')
        else:
            msg_context.append(f'**`[-----]`** {msg.author}: {msg.content}')

        after = []
        for _ in range(2):  # Get next 2 messages within 10s
            try:
                next_msg = await self.bot.wait_for('message', check=(lambda m: m.channel == message.channel), timeout=5)
            except TimeoutError:
                pass
            else:
                msg_context.append(f'`[+{str(abs(now-next_msg.created_at)).split(".")[0][3:]}]` {next_msg.author}: {next_msg.content}')
                after.append(next_msg)

        recent_msgs = [msg for msg in prev_msgs if (datetime.utcnow() - msg.created_at).seconds < 120] # List of messages from last 2 minutes
        return ('\n'.join(msg_context), recent_msgs, after)

    async def _dm_highlight(self, message: discord.Message, key: str):

        target_ids = self.highlights.get(key)
        context, prev, after= await self._get_msg_context(message, key)

        for id in target_ids:
            if message.author.id == id:
                continue

            member = message.guild.get_member(id)

            if (member is None or not member.permissions_in(message.channel).read_messages) and id != self.bot.owner_id:
                continue

            if any([msg.author.id == id for msg in after]):
                continue

            if not self.ignore_check(message, id):
                continue

            ignore = self.ignores.get(id)

            if ignore:
                users_to_ignore = ignore.get('users', [])
            else:
                users_to_ignore = []

            if any([msg.author.id == id for msg in prev]):  # If target recently spoke, no DM
                continue

            if any([(key.lower() in msg.content.lower() and msg.author.id not in users_to_ignore) for msg in prev[:-1]]):  # No need to spam highlights
                continue

            e = discord.Embed(title=f'You were mentioned in {message.guild} | #{message.channel}',
                              description=f'{context}\n'
                                          f'[Jump to message]({message.jump_url})',
                              color=discord.Color(0x00B0F4),
                              timestamp=datetime.utcnow())
            e.set_footer(text=f'Highlight word: {key}')
            try:
                await member.send(embed=e)
            except discord.Forbidden as err:
                if 'Cannot send messages to this user' in err.text:
                    await self.bot.get_user(self.bot.owner_id).send(f'Missing permission highlight to {member}, removing...\n```{err}```')
                    for val in self.highlights.values():
                        try:
                            val.remove(id)
                        except ValueError:
                            pass

    async def _dm_mention(self, message, _id):
        context, prev, after = await self._get_msg_context(message, _id, True)

        if any([user.id == _id for msg in prev[:-1] for user in msg.mentions]):
            return

        if any([msg.author.id == _id for msg in after]):
            return

        if not self.ignore_check(message, _id):
            return

        e = discord.Embed(title=f'You were mentioned in {message.guild} | #{message.channel}',
                          description=f'{context}\n'
                                      f'[Jump to message]({message.jump_url})',
                          color=discord.Color(0xFAA61A),
                          timestamp=datetime.utcnow())

        target = self.bot.get_user(_id)
        if target is None:
            return
        try:
            await target.send(embed=e)
        except discord.Forbidden as err:
            if 'Cannot send messages to this user' in err.text:
                await self.bot.get_user(self.bot.owner_id).send(f'Missing permission highlight to {target}, removing...\n```{err}```')
                self.mentions.remove(_id)
        else:
            try:
                await message.add_reaction('\U0001f440')  # eyes
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        for key in self.highlights:
            if key in message.content.lower():
                await self._dm_highlight(message, key)

        for user in message.mentions:
            if user.id in self.mentions and user != message.author:
                await self._dm_mention(message, user.id)

    @commands.group(aliases=['hl'])
    async def highlight(self, ctx):
        """Get DMs for keywords and mentions!"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @highlight.command()
    async def add(self, ctx, *, key):
        """Add a highlight keyword"""
        key = key.lower()
        users = self.highlights.setdefault(key, [])
        if ctx.author.id in users:
            return await ctx.send('You already have this key registered!', delete_after=10)
        else:
            users.append(ctx.author.id)
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
            await ctx.send(f'Successfully added highlight key: {key}', delete_after=10)


    @highlight.command()
    async def remove(self, ctx, *, key):
        """Remove a highlight keyword"""
        key = key.lower()
        if key not in self.highlights:
            return await ctx.send('Sorry, I cannot find this key')
        if ctx.author.id not in self.highlights[key]:
            return await ctx.send('Sorry, you do not seem to have this key registered.', delete_after=5)
        try:
            self.highlights[key].remove(ctx.author.id)
            if not self.highlights[key]:
                del self.highlights[key]
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

        keys = '\n'.join([k for k, v in self.highlights.items() if target in v])
        if keys:
            e = discord.Embed(color=discord.Color.dark_orange(),
                              description=keys,
                              title='Highlight keys')
        else:
            e = discord.Embed(color=discord.Color.dark_orange(),
                              description='You do not have any highlight keys')
        e.add_field(name='Mentions', value="ON" if target in self.mentions else "OFF")
        e.set_author(name=user, icon_url=user.avatar_url)

        await ctx.message.add_reaction('\U00002705')  # React with checkmark
        await ctx.send(embed=e, delete_after=15)

    @highlight.command()
    async def mention(self, ctx):
        """Toggle highlight for mentions"""
        if ctx.author.id in self.mentions:
            self.mentions.remove(ctx.author.id)
            await ctx.send('You will no longer get a DM when I see you mentioned', delete_after=10)
            await ctx.message.add_reaction('\U00002796')  # React with heavy minus sign
        else:
            self.mentions.add(ctx.author.id)
            await ctx.send('You will now get a DM when I see you mentioned', delete_after=10)
            await ctx.message.add_reaction('\U00002795')  # React with heavy plus sign

    @highlight.command()
    async def clear(self, ctx):
        """Remove all highlight keys and stop highlights for mentions"""
        for val in self.highlights.values():
            try:
                val.remove(ctx.author.id)
            except ValueError:
                pass
        to_del = [key for key in self.highlights if not self.highlights[key]]  # List of keys that point to an empty list
        for key in to_del:
            del self.highlights[key]

        if ctx.author.id in self.mentions:
            self.mentions.remove(ctx.author.id)

        await ctx.message.add_reaction('\U00002705')  # React with checkmark

    @highlight.command(name='ignore')
    async def toggle_ignore(self, ctx, target: Union[discord.User, discord.TextChannel, str]):
        """Toggle ignores for highlight"""

        _ignore = self.ignores.setdefault(ctx.author.id, {})
        if isinstance(target, discord.User):
            users = _ignore.setdefault('users', [])
            if target.id not in users:
                users.append(target.id)
                await ctx.send(f'Ignoring highlights from {target}', delete_after=10)
                await ctx.message.add_reaction('\U00002795')  # React with heavy plus sign
            else:
                users.remove(target.id)
                await ctx.send(f'No longer ignoring highlights from {target}', delete_after=8)
                if not _ignore['users']:
                    del _ignore['users']
                await ctx.message.add_reaction('\U00002796')  # React with heavy minus sign
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

        elif isinstance(target, discord.TextChannel):
            channels = _ignore.setdefault('channels', [])
            if target.id not in channels:
                channels.append(target.id)
                await ctx.send(f'Ignoring highlights from {target}', delete_after=10)
                await ctx.message.add_reaction('\U00002795')  # React with heavy plus sign
            else:
                channels.remove(target.id)
                await ctx.send(f'No longer ignoring highlights from {target}!', delete_after=8)
                if not _ignore['channels']:
                    del _ignore['channels']
                await ctx.message.add_reaction('\U00002796')  # React with heavy minus sign
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

        elif isinstance(target, str) and target == 'GUILD':
            if ctx.guild is None:
                return await ctx.send('This can only be used in a guild!', delete_after=7)
            guilds = _ignore.setdefault('guilds', [])
            if ctx.guild.id not in guilds:
                guilds.append(ctx.guild.id)
                await ctx.send(f'Ignoring highlights from {ctx.guild}', delete_after=10)
                await ctx.message.add_reaction('\U00002795')  # React with heavy plus sign
            else:
                guilds.remove(ctx.guild.id)
                await ctx.send(f'No longer ignoring highlights from {ctx.guild}!', delete_after=8)
                if not _ignore['guilds']:
                    del _ignore['guilds']
                await ctx.message.add_reaction('\U00002796')  # React with heavy minus sign
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

        elif target == 'CLEAR':
            if ctx.author.id in self.ignores:
                del self.ignores[ctx.author.id]
            await ctx.send('Clearing all ignores', delete_after=5)
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

        else:
            await ctx.send('Unable to find target to ignore, please try again', delete_after=5)

        if target != 'CLEAR' and not _ignore:
            del self.ignores[ctx.author.id]

    @highlight.command(name='ignores', aliases=['listignores'])
    async def list_ignores(self, ctx):
        """List all your current ignores"""
        _ignores = self.ignores.get(ctx.author.id)
        if _ignores:
            e = discord.Embed(color=discord.Color.dark_blue(),
                              title='Highlight ignores')
            if 'guilds' in _ignores:
                guilds = '\n'.join([str(self.bot.get_guild(gid)) for gid in _ignores['guilds']])
                e.add_field(name='Guilds', value=guilds)
            if 'channels' in _ignores:
                channels = '\n'.join([str(self.bot.get_channel(cid)) for cid in _ignores['channels']])
                e.add_field(name='Channels', value=channels)
            if 'users' in _ignores:
                users = '\n'.join([str(self.bot.get_user(uid)) for uid in _ignores['users'] if self.bot.get_user(uid)])
                e.add_field(name='Users', value=users)
            await ctx.send(embed=e, delete_after=15)

        else:
            await ctx.send('You do not have ignores set!', delete_after=5)


    @highlight.command()
    @commands.is_owner()
    async def save(self, ctx):
        try:
            self.save_highlights()
            self.save_mentions()
            self.save_ignores()
        except:
            await ctx.send('An error has occurred ')
        else:
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

    # noinspection PyCallingNonCallable
    @tasks.loop(hours=24)
    async def save_to_json(self):
        self.save_highlights()
        self.save_mentions()
        self.save_ignores()

    def cog_unload(self):
        self.save_to_json.cancel()
        self.save_highlights()
        self.save_mentions()
        self.save_ignores()


def setup(bot):
    bot.add_cog(HighlightCog(bot))
