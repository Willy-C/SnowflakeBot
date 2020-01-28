import discord
from discord.ext import commands, tasks

import json
import re
import random
from datetime import datetime, timedelta
from asyncio import TimeoutError
from typing import Union

from utils.global_utils import confirm_prompt


class HighlightCog(commands.Cog, name='Highlight'):

    def __init__(self, bot):
        self.bot = bot
        with open('data/highlights.json') as f:
            convert_keys = lambda d: {int(k): convert_keys(v) if isinstance(v, dict) else v for (k, v) in d.items()}
            self.data = convert_keys(json.load(f))
        with open('data/mentions.json') as f:
            self.mentions = set(json.load(f))
        with open('data/highlightignores.json') as f:
            self.ignores = {int(k): v for k, v in json.load(f).items()}
        self.highlights = {}
        self.save_to_json.start()
        self.bot.loop.create_task(self.populate_cache())

    def create_regex(self, words):
        return re.compile(r'\b(?:' + '|'.join(map(re.escape, words)) + r')\b', re.IGNORECASE)

    def update_regex(self, ctx):
        guild_hl = self.highlights.setdefault(ctx.guild.id, {})
        guild_hl[ctx.author.id] = self.create_regex(self.data[ctx.guild.id][ctx.author.id])

    def create_guild_regex(self, guild_id: int):
        guild_regex = {}
        for mid in self.data[guild_id]:
            guild_regex[mid] = self.create_regex(self.data[guild_id][mid])
        return guild_regex

    async def populate_cache(self):
        await self.bot.wait_until_ready()
        for guild_id in self.data:
            self.highlights[guild_id] = self.create_guild_regex(guild_id)

    def ignore_check(self, msg, id):
        if msg.author.id == id:
            return False
        ignores = self.ignores.get(id)
        if ignores:
            if msg.author.id in ignores.get('users', []):
                return False
            if msg.channel.id in ignores.get('channels', []):
                return False
        return True

    def is_active(self, recent_msgs, member_id, word):
        if any([msg.author.id == member_id for msg in recent_msgs]):  # user recently spoke
            return True

        ignore = self.ignores.get(member_id)
        if ignore:
            users_to_ignore = ignore.get('users', [])
        else:
            users_to_ignore = []
        trigger = re.compile(r'\b' + word + r'\b', re.IGNORECASE)
        if any([trigger.search(msg.content) and msg.author.id not in users_to_ignore for msg in recent_msgs]):  # Recently highlighted
            return True
        return False

    async def get_msg_context(self, message, member_id, word, is_mention=False):
        now = datetime.utcnow()
        prev_msgs = await message.channel.history(after=(now-timedelta(minutes=5))).flatten()  # Grabs all messages from the last 5 minutes
        msg_context = []
        recent_msgs = [msg for msg in prev_msgs[:-1] if (now - msg.created_at).seconds <= 90]  # List of messages from last 90 seconds

        if not is_mention:
            if self.is_active(recent_msgs, member_id, word):
                return
        else:
            if any([user.id == member_id for msg in recent_msgs for user in msg.mentions]):
                return

        for msg in prev_msgs[-4:-1]:
            msg_context.append(f'`[-{str(abs(now-msg.created_at)).split(".")[0][3:]}]` {msg.author}: {msg.content}')

        if not is_mention:
            bolded = re.sub(f'({word})', r'**\1**', message.content, flags=re.IGNORECASE)
            msg_context.append(f'**`[-----]`** {message.author}: {bolded}')
        else:
            msg_context.append(f'**`[-----]`** {message.author}: {message.content}')

        after = []
        def check(msg):
            if msg.channel == message.channel:
                msg_context.append(f'`[+{str(abs(now - msg.created_at)).split(".")[0][3:]}]` {msg.author}: {msg.content}')
                after.append(msg)
            return len(after) == 2

        try:
            await self.bot.wait_for('message', check=check, timeout=10)
        except TimeoutError:
            pass

        if any([msg.author.id == member_id for msg in after]):
            return
        return '\n'.join(msg_context)

    async def dm_highlight(self, message, member_id: int, word: str):
        member = message.guild.get_member(member_id)
        if member is None:
            del self.highlights[message.guild.id][member_id]
            return
        if not member.permissions_in(message.channel).read_messages and member_id != self.bot.owner_id:
            return
        context = await self.get_msg_context(message, member_id, word)
        if context is None:
            return

        e = discord.Embed(title=f'You were mentioned in {message.guild} | #{message.channel}',
                          description=f'{context}\n'
                                      f'[Jump to message]({message.jump_url})',
                          color=discord.Color(0x00B0F4),
                          timestamp=datetime.utcnow())
        e.set_footer(text=f'Highlight word: {word}')
        try:
            await member.send(embed=e)
        except discord.Forbidden as err:
            if 'Cannot send messages to this user' in err.text:
                await self.bot.get_user(self.bot.owner_id).send(f'Missing permissions to DM {member}\n```{err}```')

    async def dm_mention(self, message, member_id):
        member = message.guild.get_member(member_id)
        if (member is None or not member.permissions_in(message.channel).read_messages) and id != self.bot.owner_id:
            return
        context = await self.get_msg_context(message, member_id, None, is_mention=True)
        if context is None:
            return
        e = discord.Embed(title=f'You were mentioned in {message.guild} | #{message.channel}',
                          description=f'{context}\n'
                                      f'[Jump to message]({message.jump_url})',
                          color=discord.Color(0xFAA61A),
                          timestamp=datetime.utcnow())

        target = self.bot.get_user(member_id)
        try:
            await target.send(embed=e)
        except (discord.Forbidden, AttributeError) as err:
            if 'Cannot send messages to this user' in err.text:
                await self.bot.get_user(self.bot.owner_id).send(f'Failed to DM {target}|{member_id}\n```{err}```')
        else:
            try:
                reactions = ['<a:angeryping:667541695755190282>',
                             '<a:hammerping:656983551429967896>',
                             '<:eyes:644633489727291402>,',
                             '<:dabJuicy:667892769053736981>',
                             '<:angryJuicy:669305873562206211>',
                             '<a:bap:667465646384218122>']
                await message.add_reaction(random.choice(reactions))
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None or message.guild.id not in self.highlights or message.webhook_id is not None:
            return
        for mid, regex in self.highlights[message.guild.id].items():
            if not self.ignore_check(message, mid):
                continue
            match = regex.search(message.content)
            if match:
                self.bot.loop.create_task(self.dm_highlight(message, mid, match.group()))

        for user in message.mentions:
            if user.id in self.mentions and user != message.author:
                if self.ignore_check(message, user.id):
                    self.bot.loop.create_task(self.dm_mention(message, user.id))

    @commands.group(aliases=['hl'], case_insensitive=True)
    async def highlight(self, ctx):
        """Highlight is an attempt to emulate Skype's word highlighting feature.
        Useful for allowing you to only get notifications when specific words are used.
        This works by sending a DM to you with the message context when your word is used.
        Additionally, I can send you a DM when I see you get pinged.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @highlight.command()
    @commands.guild_only()
    async def add(self, ctx, keyword):
        """Add a highlight keyword for the current server"""
        key = keyword.lower()
        if len(key) < 3:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            return await ctx.send('Keywords must be at least 3 characters!')
        guild_hl = self.data.setdefault(ctx.guild.id, {})
        member_hl = guild_hl.setdefault(ctx.author.id, [])
        if key in member_hl:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            return await ctx.send('You already have this keyword added!', delete_after=10)
        else:
            member_hl.append(key)
            self.update_regex(ctx)
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
            await ctx.send(f'Successfully added highlight key: {key}', delete_after=10)

    @highlight.command()
    @commands.guild_only()
    async def remove(self, ctx, keyword):
        """Remove a highlight keyword for the current server"""
        key = keyword.lower()
        guild_hl = self.data.get(ctx.guild.id)
        if not guild_hl:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            return await ctx.send(f'No highlights found for {ctx.guild}', delete_after=5)
        member_hl = guild_hl.get(ctx.author.id)
        if member_hl is None:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            return await ctx.send(f'Sorry, you do not seem to have any keywords added for {ctx.guild}', delete_after=10)
        if key not in member_hl:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            return await ctx.send('Sorry, you do not seem to have this keyword added', delete_after=10)
        member_hl.remove(key)
        if not member_hl:
            del self.data[ctx.guild.id][ctx.author.id]
            del self.highlights[ctx.guild.id][ctx.author.id]
            if not self.data[ctx.guild.id]:
                del self.data[ctx.guild.id]
                del self.highlights[ctx.guild.id]
        else:
            self.update_regex(ctx)
        await ctx.message.add_reaction('\U00002705')  # React with checkmark
        await ctx.send(f'Successfully removed  highlight key: `{key}`', delete_after=10)

    @highlight.command(name='import')
    @commands.guild_only()
    async def _import(self, ctx, *, guild: Union[int, str]):
        """Import your highlight words from another server."""
        g = self.bot.get_guild(guild)
        if g is None:
            g = discord.utils.get(self.bot.guilds, name=str(guild))
        if g is not None:
            if g.id in self.data and ctx.author.id in self.data[g.id]:
                guild_hl = self.data.setdefault(ctx.guild.id, {})
                guild_hl[ctx.author.id] = self.data[g.id][ctx.author.id]
                self.update_regex(ctx)
                await ctx.message.add_reaction('\U00002705')  # React with checkmark
                await ctx.send(f'Imported your highlights from {g}', delete_after=7)
        else:
            await ctx.send('Unable to find server with that name or ID', delete_after=7)
            await ctx.message.add_reaction('<:redTick:602811779474522113>')

    @highlight.command()
    async def list(self, ctx):
        """List your highlight words for the current guild
        If used in DM, all words from all guilds will be given"""
        delete_after = 15
        if ctx.guild is None:
            all_hl = []
            for guild in self.data:
                if ctx.author.id in self.data[guild]:
                    all_hl.append(f'**__{self.bot.get_guild(guild)}__**')
                    all_hl.extend(self.data[guild][ctx.author.id])
            keys = '\n'.join(all_hl)
            delete_after = None
        elif ctx.guild.id in self.data and ctx.author.id in self.data[ctx.guild.id]:
            keys = '\n'.join(self.data[ctx.guild.id][ctx.author.id])
        else:
            keys = 'You do not have any highlight words here'

        e = discord.Embed(color=discord.Color.dark_orange(),
                          title=f'Highlights for {ctx.guild}',
                          description=keys)
        e.add_field(name='Mentions', value="ON" if ctx.author.id in self.mentions else "OFF")
        e.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

        await ctx.message.add_reaction('\U00002705')  # React with checkmark
        await ctx.send(embed=e, delete_after=delete_after)

    @highlight.command()
    async def mention(self, ctx):
        """Toggle highlight for mentions"""
        if ctx.author.id in self.mentions:
            self.mentions.remove(ctx.author.id)
            await ctx.send('You will no longer get a DM when I see you mentioned', delete_after=10)
            await ctx.message.add_reaction('\U00002796')  # React with minus sign
        else:
            self.mentions.add(ctx.author.id)
            await ctx.send('You will now get a DM when I see you mentioned', delete_after=10)
            await ctx.message.add_reaction('\U00002795')  # React with plus sign

    @highlight.command()
    async def clear(self, ctx):
        """Clear all highlight words for the current guild
        If used in DM, clears all words from all guilds
        Note: This will also disable highlight for mentions/pings"""
        if ctx.guild is None:
            if not await confirm_prompt(ctx, 'Clear all highlight words?'):
                return
            to_del = []
            for guild_id in self.data:
                if ctx.author.id in self.data[guild_id]:
                    del self.data[guild_id][ctx.author.id]
                    del self.highlights[guild_id][ctx.author.id]
                    if not self.data[guild_id]:
                        to_del.append(guild_id)
            for guild_id in to_del:
                del self.data[guild_id]
                del self.highlights[guild_id]
            await ctx.send(f'Cleared all of your highlight words')
        elif ctx.guild.id in self.data and ctx.author.id in self.data[ctx.guild.id]:
            if not await confirm_prompt(ctx, f'Clear all highlight words for {ctx.guild}?'):
                return
            del self.data[ctx.guild.id][ctx.author.id]
            del self.highlights[ctx.guild.id][ctx.author.id]
            if not self.data[ctx.guild.id]:
                del self.data[ctx.guild.id]
                del self.highlights[ctx.guild.id]
            await ctx.send(f'Cleared all of your highlight words for {ctx.guild}', delete_after=7)
        else:
            await ctx.send(f'You do not have any highlight words for {ctx.guild}', delete_after=7)

        if ctx.author.id in self.mentions:
            self.mentions.remove(ctx.author.id)
        await ctx.message.add_reaction('\U00002705')

    @highlight.command(name='ignore')
    async def toggle_ignore(self, ctx, target: Union[discord.User, discord.TextChannel, str]):
        """Toggle ignores for highlight
        Can enter a User, TextChannel via mention, ID or name"""
        ignores = self.ignores.setdefault(ctx.author.id, {})
        if isinstance(target, discord.User):
            users = ignores.setdefault('users', [])
            if target.id not in users:
                users.append(target.id)
                await ctx.send(f'Ignoring highlights from {target}', delete_after=7)
                await ctx.message.add_reaction('\U00002795')  # React with plus sign
            else:
                users.remove(target.id)
                await ctx.send(f'No longer ignoring highlights from {target}', delete_after=7)
                if not ignores['users']:
                    del ignores['users']
                await ctx.message.add_reaction('\U00002796')  # React with minus sign
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

        elif isinstance(target, discord.TextChannel):
            channels = ignores.setdefault('channels', [])
            if target.id not in channels:
                channels.append(target.id)
                await ctx.send(f'Ignoring highlights from {target}', delete_after=7)
                await ctx.message.add_reaction('\U00002795')  # React with plus sign
            else:
                channels.remove(target.id)
                await ctx.send(f'No longer ignoring highlights from {target}!', delete_after=7)
                if not ignores['channels']:
                    del ignores['channels']
                await ctx.message.add_reaction('\U00002796')  # React with minus sign
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
        else:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            await ctx.send('Unable to find target to ignore, please enter a users or a text channel', delete_after=7)
        if not ignores:
            del self.ignores[ctx.author.id]

    @highlight.command(name='ignores', aliases=['listignores'])
    async def list_ignores(self, ctx):
        """List your current ignores"""
        ignores = self.ignores.get(ctx.author.id)
        if ignores:
            e = discord.Embed(color=discord.Color.dark_blue(),
                              title='Highlight ignores')
            if 'channels' in ignores:
                channels = '\n'.join([str(self.bot.get_channel(cid)) for cid in ignores['channels']])
                e.add_field(name='Channels', value=channels)
            if 'users' in ignores:
                users = '\n'.join([str(self.bot.get_user(uid)) for uid in ignores['users'] if self.bot.get_user(uid)])
                e.add_field(name='Users', value=users)
            await ctx.send(embed=e, delete_after=15)
        else:
            await ctx.send('You do not have ignores set!', delete_after=5)
        await ctx.message.add_reaction('\U00002705')  # React with checkmark

    def save_highlights(self):
        with open('data/highlights.json', 'w') as f:
            json.dump(self.data, f, indent=2)

    def save_mentions(self):
        with open('data/mentions.json', 'w') as f:
            json.dump(list(self.mentions), f, indent=2)

    def save_ignores(self):
        with open('data/highlightignores.json', 'w') as f:
            json.dump(self.ignores, f, indent=2)

    @highlight.command()
    @commands.is_owner()
    async def save(self, ctx):
        try:
            self.save_highlights()
            self.save_mentions()
            self.save_ignores()
        except Exception as e:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            await ctx.send(f'An error has occurred\n```{e}```')
        else:
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

    # noinspection PyCallingNonCallable
    @tasks.loop(hours=48)
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
