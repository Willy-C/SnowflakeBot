from __future__ import annotations

import re
import logging
import asyncio
from typing import Union
from asyncio import TimeoutError
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional, Literal

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

from utils.fuzzy import finder
from utils.cache import ExpiringCache

if TYPE_CHECKING:
    from main import SnowflakeBot
    from utils.context import Context


log = logging.getLogger(__name__)


REPLIES_SETTINGS_TEXT = {
    0: 'Off',
    1: 'On: Always',
    2: 'On: Only when not pinged'
}


class Highlights(commands.Cog):
    highlights: dict[int, dict[int, re.Pattern]]  # guild_id: {user_id: re.Pattern}
    ignores: dict[int, defaultdict[str, list[int]]]  # user_id: {user/channel: [target_ids]}
    replies: dict[int, int]  # user_id: setting (0 = off, 1 = on always, 2 = no pings only)

    def __init__(self, bot: SnowflakeBot):
        self.bot: SnowflakeBot = bot
        self.highlights = defaultdict(dict)
        self.ignores = defaultdict(lambda: defaultdict(list))
        self.replies = {}
        self.recent_triggers = ExpiringCache(seconds=60)
        self.bot.loop.create_task(self.populate_cache())

    def create_user_regex(self, words) -> re.Pattern:
        return re.compile(r'\b(' + '|'.join(map(re.escape, words)) + r')s?\b', re.IGNORECASE)

    async def make_guild_cache(self, records: list[asyncpg.Record]) -> dict[int, re.Pattern]:
        collect_words = defaultdict(list)
        for record in records:
            collect_words[record['id']].append(record['word'])

        return {user_id: self.create_user_regex(words) for user_id, words in collect_words.items()}

    async def fetch_all_highlights(self) -> None:
        query = '''SELECT id, word FROM highlights WHERE guild=$1;'''
        for guild in self.bot.guilds:
            records = await self.bot.pool.fetch(query, guild.id)
            if not records:
                continue
            self.highlights[guild.id] = await self.make_guild_cache(records)

    async def fetch_ignores(self) -> None:
        query = '''SELECT * FROM hl_ignores;'''
        records = await self.bot.pool.fetch(query)
        for r in records:
            self.ignores[r['id']][r['type']].append(r['target'])

    async def fetch_dm_mentions(self) -> None:
        query = '''SELECT * FROM hl_replies;'''
        records = await self.bot.pool.fetch(query)
        for record in records:
            self.replies[record['id']] = record['state']

    async def populate_cache(self) -> None:
        await self.fetch_all_highlights()
        await self.fetch_ignores()
        await self.fetch_dm_mentions()

    async def delete_highlights(self, user_id: int, guild_id: int) -> None:
        query = '''DELETE FROM highlights WHERE id=$1 AND guild=$2;'''
        await self.bot.pool.execute(query, user_id, guild_id)
        self.highlights[guild_id].pop(user_id, None)
        if not self.highlights[guild_id]:
            self.highlights.pop(guild_id, None)

    async def delete_replies(self, user_id: int) -> None:
        query = '''DELETE FROM hl_replies WHERE id=$1;'''
        await self.bot.pool.execute(query, user_id)
        self.replies.pop(user_id, None)

    async def update_user_highlights(self, user_id: int, guild_id: int):
        query = '''SELECT word FROM highlights WHERE guild=$1 AND id=$2;'''
        records = await self.bot.pool.fetch(query, guild_id, user_id)
        if not records:
            self.highlights[guild_id].pop(user_id, None)
            if not self.highlights[guild_id]:
                self.highlights.pop(guild_id, None)
            return
        self.highlights[guild_id][user_id] = self.create_user_regex([r['word'] for r in records])

    async def update_user_ignores(self, user_id: int):
        query = '''SELECT type, target FROM hl_ignores WHERE id=$1;'''
        records = await self.bot.pool.fetch(query, user_id)
        if not records:
            self.ignores.pop(user_id, None)
            return
        for r in records:
            self.ignores[user_id][r['type']].append(r['target'])

    def should_ignore(self, user_id: int, message: discord.Message) -> bool:
        """Check if message should be ignored, returns True if it should be ignored"""
        if message.author.id == user_id:
            return True

        ignores = self.ignores.get(user_id)
        if ignores:
            if message.author.id in ignores.get('user', []):
                return True
            elif message.channel.id in ignores.get('channel', []):
                return True
        return False

    async def get_msg_context(self, message: discord.Message, minutes: int = 5, limit: int = 50) -> tuple[list[discord.Message], list[discord.Message]]:
        """Get the context of a message, returns a tuple of previous and recent messages"""
        now = message.created_at

        # get all messages within the last few minutes, default 5
        prev = [msg async for msg in message.channel.history(limit=limit, after=now - timedelta(minutes=minutes))]

        # get all messages within last 40 seconds, we will filter from our previous list to save an API call
        # recent_messages = [msg for msg in prev_messages[:-1] if (now - msg.created_at).seconds <= recent]

        after = []

        def check(msg: discord.Message):
            if msg.channel == message.channel:
                after.append(msg)
            return len(after) == 3

        try:
            await self.bot.wait_for('message', check=check, timeout=20)
        except TimeoutError:
            pass

        return prev, after

    def format_message(self, message: discord.Message, bold: bool = False, word: str = None) -> str:
        """Formats a message for the highlight. Bolds the trigger message and word"""
        created = discord.utils.format_dt(message.created_at, "T")

        author = message.author
        if author.global_name and author.global_name != author.name:
            fmt_author = discord.utils.escape_markdown(f'{author.global_name} (@{author})')
        else:
            fmt_author = discord.utils.escape_markdown(str(author))

        if not message.content:
            if len(message.attachments) == 1:
                content = message.attachments[0].url
            elif len(message.attachments) > 1:
                content = f'{len(message.attachments)} attachments'
            else:
                content = 'No content'
        else:
            content = message.content

        if bold:
            if word:
                content = re.sub(f'({word})', r'**\1**', content, flags=re.IGNORECASE)
            return f'**[{created}]** {fmt_author}: {content}'

        return f'[{created}] {fmt_author}: {content}'

    def build_full_context(self, prev: list[discord.Message], after: list[discord.Message], word: Optional[str]) -> str:
        context = []

        for msg in prev[-4:-1]:
            context.append(self.format_message(msg))

        context.append(self.format_message(prev[-1], bold=True, word=word))

        for msg in after:
            context.append(self.format_message(msg))

        return '\n'.join(context)

    async def _send_highlight_dm(self, user_id: int, embed: discord.Embed, message: discord.Message, word: str) -> None:
        try:
            user = self.bot.get_user(user_id) or (await self.bot.fetch_user(user_id))
            await user.send(embed=embed)
        except discord.NotFound:
            log.info('User %s not found, deleting highlights and replies permanently', user_id)
            await self.delete_highlights(user_id, message.guild.id)
            await self.delete_replies(user_id)
            return
        except discord.Forbidden as e:
            if "Cannot send messages to this user" in e.text:
                log.info('User %s has DMs disabled, deleting highlights and replies from cache', user_id)
                self.highlights[message.guild.id].pop(user_id, None)
                self.replies.pop(user_id, None)
                # await self.delete_highlights(user_id, message.guild.id)
                # await self.delete_replies(user_id)
                return
        else:
            log.info('Sent highlight notification to %s in %s for %s', user_id, message.channel.id, word)

    async def send_highlight_notif(self, message: discord.Message, user_id: int, word: str, prev: list[discord.Message], after: list[discord.Message]) -> None:
        now = message.created_at
        recent_messages = [msg for msg in prev[:-1] if (now - msg.created_at).seconds <= 40]

        if any(msg.author.id == user_id for msg in recent_messages):
            return

        if (message.channel.id, user_id, word.lower()) in self.recent_triggers:
            return
        self.recent_triggers[(message.channel.id, user_id, word.lower())] = True

        context = self.build_full_context(prev, after, word)

        embed = discord.Embed(
            title=f'You were mentioned in {message.guild} | #{message.channel}',
            description=f'{context}\n[Jump to message]({message.jump_url})',
            colour=0x00B0F4,
            timestamp=now
        )
        embed.set_footer(text=f'Highlight trigger: {word}')

        await self._send_highlight_dm(user_id, embed, message, word)

    async def send_reply_notification(self, message: discord.Message, user_id: int, word: None, prev: list[discord.Message], after: list[discord.Message]) -> None:
        now = message.created_at
        recent_messages = [msg for msg in prev[:-1] if (now - msg.created_at).seconds <= 40]
        # If this is a reply highlight, check their reply settings
        # 0 = off, 1 = on always, 2 = only when not pinged
        setting = self.replies[user_id]
        if setting == 0:
            log.info('User %s has highlight replies set to 0 but was in cache', user_id)
            await self.delete_replies(user_id)
            return
        elif setting == 2:
            if any(u.id == user_id for u in message.mentions):
                return

        if any(msg.author.id == user_id for msg in recent_messages):
            return

        if (message.channel.id, user_id, word) in self.recent_triggers:
            return
        self.recent_triggers[(message.channel.id, user_id, word)] = True

        context = self.build_full_context(prev, after, word)

        embed = discord.Embed(
            title=f'You were replied to in {message.guild} | #{message.channel}',
            description=f'{context}\n[Jump to message]({message.jump_url})',
            colour=0xFAA61A,
            timestamp=now
        )
        embed.set_footer(text='Replied at')

        if isinstance(message.reference.resolved, discord.Message):
            ref = message.reference.resolved.jump_url
            embed.description += f' | [Replying to]({ref})'

        await self._send_highlight_dm(user_id, embed, message, 'reply')

    async def wait_for_activity(self, message: discord.Message, user_ids: set[int], timeout: int = 20) -> set[int]:
        """Wait for activity from a list of user_ids"""
        active = set()

        # We will leverage the check functions to just add the user into the active set
        # and return False to keep the wait_for running for the full timeout
        def message_check(m: discord.Message):
            if m.author.id in user_ids and m.channel == message.channel:
                active.add(m.author.id)
            return False

        def typing_check(c: discord.abc.Messageable, u: discord.User, w: datetime):
            if u.id in user_ids and c == message.channel:
                active.add(u.id)
            return False

        def reaction_check(r: discord.Reaction, u: discord.Member):
            if u.id in user_ids and r.message.channel == message.channel:
                active.add(u.id)
            return False

        tasks_names = [
            ('message', message_check),
            ('typing', typing_check),
            ('reaction_add', reaction_check)
        ]
        tasks = [asyncio.create_task(self.bot.wait_for(name, check=check)) for name, check in tasks_names]
        done, pending = await asyncio.wait(tasks, timeout=timeout)
        # these tasks never complete since all our checks return False
        for task in tasks:
            try:
                # task.add_done_callback(lambda f: f.exception())
                task.cancel()
            except Exception:
                pass

        return active

    async def handle_highlights(self, message: discord.Message, highlights: dict[int, Optional[str]]) -> None:
        """Handle highlights"""
        filtered = {user_id: word for user_id, word in highlights.items() if not self.should_ignore(user_id, message)}
        if not filtered:
            return
        active_task = self.bot.loop.create_task(self.wait_for_activity(message, set(filtered.keys()), timeout=20))
        prev, after = await self.get_msg_context(message, minutes=5)
        active_users = await active_task
        for user_id, word in filtered.items():
            if user_id in active_users:
                continue
            if word:
                self.bot.loop.create_task(self.send_highlight_notif(message, user_id, word, prev, after))
            else:
                self.bot.loop.create_task(self.send_reply_notification(message, user_id, word, prev, after))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot or message.webhook_id is not None:
            return

        to_send = {}
        if message.guild.id in self.highlights:
            for member_id, regex in self.highlights[message.guild.id].items():
                match = regex.search(message.content)
                if match:
                    to_send[member_id] = match.group(0)

        if message.type is discord.MessageType.reply:
            if message.reference and isinstance(message.reference.resolved, discord.Message):
                replied_author = message.reference.resolved.author.id
                if replied_author in self.replies and replied_author not in to_send:
                    to_send[replied_author] = None

        if to_send:
            await self.handle_highlights(message, to_send)

    @commands.hybrid_group(aliases=['hl'])
    @commands.guild_only()
    async def highlight(self, ctx: Context):
        """Highlight is an attempt to emulate Skype's word highlighting feature.

        This allows you to only get notifications when specific words or phrases are used.
        This works by sending a DM to you with the message context when your word is used.
        Additionally, I can send you a DM when someone replies to your message with the built-in reply feature.
        """
        await ctx.send_help(ctx.command)

    @highlight.command(name='add')
    @app_commands.describe(trigger='The trigger to add, not case-sensitive')
    async def highlight_add(self, ctx: Context, *, trigger: commands.Range[str, 2]):
        """Add a highlight word or phrase
        Triggers are not case-sensitive"""
        trigger = trigger.lower()
        query = '''INSERT INTO highlights(id, guild, word) VALUES($1, $2, $3);'''
        try:
            await self.bot.pool.execute(query, ctx.author.id, ctx.guild.id, trigger)
        except asyncpg.UniqueViolationError:
            await ctx.send('You already have this trigger added!', ephemeral=True)
            await ctx.tick(False)
        else:
            if not ctx.interaction:
                await ctx.tick(True)
                await ctx.send(f'Successfully added trigger `{trigger}`', delete_after=7)
            else:
                await ctx.send(f'Successfully added trigger `{trigger}`', ephemeral=True)
            await self.update_user_highlights(ctx.author.id, ctx.guild.id)

    @highlight.command(name='remove')
    @app_commands.describe(trigger='The trigger to remove, not case-sensitive')
    async def highlight_remove(self, ctx: Context, *, trigger: str):
        """Remove a highlight word or phrase
        Triggers are not case-sensitive"""
        trigger = trigger.lower()
        query = '''DELETE FROM highlights WHERE id=$1 AND guild=$2 AND word=$3;'''
        result = await self.bot.pool.execute(query, ctx.author.id, ctx.guild.id, trigger)
        if result == 'DELETE 0':
            await ctx.send('You do not have this trigger added!', ephemeral=True)
            await ctx.tick(False)
        else:
            if not ctx.interaction:
                await ctx.tick(True)
                await ctx.send(f'Successfully removed trigger `{trigger}`', delete_after=7)
            else:
                await ctx.send(f'Successfully removed trigger `{trigger}`', ephemeral=True)
            await self.update_user_highlights(ctx.author.id, ctx.guild.id)

    @highlight_remove.autocomplete('trigger')
    async def highlight_remove_auto_complete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        query = '''SELECT word FROM highlights WHERE id=$1 AND guild=$2;'''
        records = await self.bot.pool.fetch(query, interaction.user.id, interaction.guild_id)
        words = [r['word'] for r in records]
        return [app_commands.Choice(name=word, value=word) for word in finder(current, words)[:25]]

    @highlight.command(name='list')
    async def highlight_list(self, ctx: Context):
        """List your highlights"""
        query = '''SELECT word FROM highlights WHERE id=$1 AND guild=$2;'''
        records = await self.bot.pool.fetch(query, ctx.author.id, ctx.guild.id)
        if not records:
            triggers = 'You do not have any highlight triggers set up!'
        else:
            triggers = '\n'.join(r['word'] for r in records)

        e = discord.Embed(title=f'Highlights for {ctx.guild}',
                          description=triggers,
                          colour=ctx.author.colour if ctx.author.colour.value != 0 else discord.Colour.blurple())

        e.add_field(name='Replies', value=REPLIES_SETTINGS_TEXT[self.replies.get(ctx.author.id, 0)], inline=False)
        e.set_author(name=ctx.author, icon_url=ctx.author.avatar.url)
        if not ctx.interaction:
            await ctx.tick(True)
            await ctx.send(embed=e, delete_after=15)
        else:
            await ctx.send(embed=e, ephemeral=True)

    @highlight.command(name='replies', with_app_command=False, aliases=['reply'])
    async def highlight_replies(self, ctx: Context, *, setting: Union[int, str]):
        """Set highlight for replies

        This will notify you when someone replies to your message
        0 = off, 1 = on always, 2 = only when not pinged
        """
        if isinstance(setting, str):
            setting = setting.lower()
        valid_setting = ['off', 'on', 'no pings', 0, 1, 2]

        if setting not in valid_setting:
            # display settings in pairs with their number
            display_settings = "\n".join(f"{v} = {k}" for k, v in REPLIES_SETTINGS_TEXT.items())
            return await ctx.send(f'Invalid setting, please use one of:\n{display_settings}')

        if isinstance(setting, str):
            setting = valid_setting.index(setting)

        query = '''INSERT INTO hl_replies(id, state) VALUES($1, $2);'''
        await self.bot.pool.execute(query, ctx.author.id, setting)
        self.replies[ctx.author.id] = setting
        await ctx.tick(True)
        await ctx.send(f'Successfully set your highlight replies to: `{REPLIES_SETTINGS_TEXT[setting]}`', delete_after=7)

    @highlight.app_command.command(name='reply')
    @app_commands.describe(setting='The setting for your highlight replies')
    @app_commands.choices(setting=[
        app_commands.Choice(name='Off', value=0),
        app_commands.Choice(name='On Always (All replies)', value=1),
        app_commands.Choice(name='No pings only (Only replies that did not ping you)', value=2),
    ])
    async def highlight_replies_slash(self, interaction: discord.Interaction, setting: app_commands.Choice[int]):
        """Set highlight for replies"""
        query = '''INSERT INTO hl_replies(id, state) VALUES($1, $2) ON CONFLICT (id) DO UPDATE SET state=$2;'''
        await self.bot.pool.execute(query, interaction.user.id, setting.value)
        self.replies[interaction.user.id] = setting.value
        await interaction.response.send_message(f'Successfully set your highlight replies to: `{setting.name}`', ephemeral=True)

    @highlight.command(name='import')
    async def highlight_import(self, ctx: Context, *, server: str):
        """Import your highlights from another server"""
        await ctx.defer(ephemeral=True)

        guild = None
        if server.isdigit():
            guild = self.bot.get_guild(int(server))
        guild = guild or discord.utils.get(ctx.author.mutual_guilds, name=server)

        if not guild:
            await ctx.send('Could not find the server with that ID or name', ephemeral=True)
            return

        query = '''SELECT word FROM highlights WHERE id=$1 AND guild=$2;'''
        records = await self.bot.pool.fetch(query, ctx.author.id, guild.id)
        if not records:
            await ctx.send('You do not have any highlights set up in that server!', ephemeral=True)
            await ctx.tick(False)
            return

        cont = await ctx.confirm_prompt(f'Are you sure you want to import {len(records)} highlights from {guild.name}?', ephemeral=True)
        if not cont:
            await ctx.send('Cancelled', ephemeral=True)
            await ctx.tick(False)
            return

        query = '''INSERT INTO highlights(id, guild, word) VALUES($1, $2, $3) ON CONFLICT DO NOTHING;'''
        for record in records:
            await self.bot.pool.execute(query, ctx.author.id, ctx.guild.id, record['word'])
        await self.update_user_highlights(ctx.author.id, ctx.guild.id)

        if not ctx.interaction:
            await ctx.tick(True)
            await ctx.send(f'Successfully imported {len(records)} highlights from {guild.name}', delete_after=7)
        else:
            await ctx.send(f'Successfully imported {len(records)} highlights from {guild.name}', ephemeral=True)

    @highlight_import.autocomplete('server')
    async def highlight_import_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        query = '''SELECT DISTINCT guild FROM highlights WHERE id=$1;'''
        records = await self.bot.pool.fetch(query, interaction.user.id)
        guild_ids = {r['guild'] for r in records}
        mutual_guilds = {g.name: str(g.id) for g in interaction.user.mutual_guilds if g.id != interaction.guild_id and g.id in guild_ids}
        keys = finder(current, mutual_guilds.keys())
        return [app_commands.Choice(name=k, value=mutual_guilds[k]) for k in keys[:25]]

    async def add_block(self, user_id: int, target_type: Literal['user', 'channel'], target_id: int):
        query = '''INSERT INTO hl_ignores(id, type, target) VALUES($1, $2, $3);'''
        await self.bot.pool.execute(query, user_id, target_type, target_id)
        self.ignores[user_id][target_type].append(target_id)

    async def remove_block(self, user_id: int, target_type: Literal['user', 'channel'], target_id: int):
        query = '''DELETE FROM hl_ignores WHERE id=$1 AND type=$2 AND target=$3;'''
        result = await self.bot.pool.execute(query, user_id, target_type, target_id)
        self.ignores[user_id][target_type].remove(target_id)
        if not self.ignores[user_id][target_type]:
            self.ignores[user_id].pop(target_type)
            if not self.ignores[user_id]:
                self.ignores.pop(user_id)
        return result

    @highlight.command(name='ignore', aliases=['block'], with_app_command=False)
    async def highlight_block(self, ctx: Context, *, target: Union[discord.User, discord.abc.GuildChannel, str]):
        """Block a user or channel from triggering your highlights"""
        if isinstance(target, str):
            # Both converters failed
            await ctx.tick(False)
            return await ctx.send('Invalid user or channel')

        if isinstance(target, discord.User):
            target_type = 'user'
            if target == ctx.author:
                await ctx.send('You cannot block yourself')
                await ctx.tick(False)
                return
        else:
            if not isinstance(target, discord.abc.Messageable):
                await ctx.send('That channel cannot receive messages')
                await ctx.tick(False)
                return
            target_type = 'channel'

        try:
            await self.add_block(ctx.author.id, target_type, target.id)
        except asyncpg.UniqueViolationError:
            await ctx.tick(False)
            await ctx.send(f'{target.mention} is already blocked from your highlights', delete_after=7, allowed_mentions=discord.AllowedMentions.none())
        else:
            await ctx.tick(True)
            await ctx.send(f'Ignoring highlights from {target.mention}', delete_after=7, allowed_mentions=discord.AllowedMentions.none())

    @highlight.app_command.command(name='block')
    async def highlight_block_slash(self, interaction: discord.Interaction, member: Optional[discord.Member], channel: Optional[discord.abc.GuildChannel]):
        """Block a user or channel from triggering your highlights"""
        if not member and not channel:
            return await interaction.response.send_message('You must provide a user or channel to block', ephemeral=True)
        if member and channel:
            return await interaction.response.send_message('Please provide a member or channel, not both', ephemeral=True)

        target = member or channel
        if isinstance(target, discord.Member):
            if target == interaction.user:
                return await interaction.response.send_message('You cannot block yourself', ephemeral=True)
            target_type = 'user'
        else:
            if not isinstance(target, discord.abc.Messageable):
                return await interaction.response.send_message('That channel cannot receive messages', ephemeral=True)
            target_type = 'channel'

        try:
            await self.add_block(interaction.user.id, target_type, target.id)
        except asyncpg.UniqueViolationError:
            return await interaction.response.send_message(f'{target.mention} is already blocked from your highlights', ephemeral=True)
        else:
            await interaction.response.send_message(f'Ignoring highlights from {target.mention}', ephemeral=True)

    @highlight.command(name='unignore', with_app_command=False, aliases=['unblock'])
    async def highlight_unblock(self, ctx: Context, *, target: Union[discord.User, discord.abc.GuildChannel, str]):
        """Unblock a previously blocked user or channel"""
        if isinstance(target, str):
            # Both converters failed
            await ctx.tick(False)
            return await ctx.send('Invalid user or channel')

        if isinstance(target, discord.User):
            target_type = 'user'
            if target == ctx.author:
                await ctx.send('You cannot block yourself')
                await ctx.tick(False)
                return
        else:
            if not isinstance(target, discord.abc.Messageable):
                await ctx.send('That channel cannot receive messages')
                await ctx.tick(False)
                return
            target_type = 'channel'

        result = await self.remove_block(ctx.author.id, target_type, target.id)
        if result == 'DELETE 0':
            await ctx.tick(False)
            await ctx.send(f'{target.mention} is not blocked from your highlights', delete_after=7, allowed_mentions=discord.AllowedMentions.none())
        else:
            await ctx.tick(True)
            await ctx.send(f'Unblocked highlights from {target.mention}', delete_after=7, allowed_mentions=discord.AllowedMentions.none())

    @highlight.app_command.command(name='unblock')
    async def highlight_unblock_slash(self, interaction: discord.Interaction, target: str):
        """Unblock a previously blocked user or channel"""
        target = int(target)
        target = (await interaction.client.get_or_fetch_user(target)) or interaction.guild.get_channel_or_thread(target)
        if not target:
            return await interaction.response.send_message('Invalid user or channel', ephemeral=True)

        if isinstance(target, discord.User):
            target_type = 'user'
            if target == interaction.user:
                return await interaction.response.send_message('You cannot block yourself', ephemeral=True)
        else:
            if not isinstance(target, discord.abc.Messageable):
                return await interaction.response.send_message('That channel cannot receive messages', ephemeral=True)
            target_type = 'channel'

        result = await self.remove_block(interaction.user.id, target_type, target.id)
        if result == 'DELETE 0':
            return await interaction.response.send_message(f'{target.mention} is not blocked from your highlights', ephemeral=True)
        else:
            await interaction.response.send_message(f'Unblocked highlights from {target.mention}', ephemeral=True)

    @highlight_unblock_slash.autocomplete('target')
    async def highlight_unblock_member_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if current.startswith('#'):
            current = current.removeprefix('#')
            query = '''SELECT target, type FROM hl_ignores WHERE id=$1 AND type='channel';'''
        elif current.startswith('@'):
            current = current.removeprefix('@')
            query = '''SELECT target, type FROM hl_ignores WHERE id=$1 AND type='user';'''
        else:
            query = '''SELECT target, type FROM hl_ignores WHERE id=$1;'''
        records = await self.bot.pool.fetch(query, interaction.user.id)

        filtered = {}
        for r in records:
            if r['type'] == 'user':
                member = interaction.guild.get_member(r['target'])
                if member:
                    filtered[f'User: {member.name} (ID: {member.id})'] = r['target']
                else:
                    filtered[f'User: Not Found (ID: {r["target"]})'] = r['target']
            else:
                channel = interaction.guild.get_channel_or_thread(r['target'])
                if channel:
                    filtered[f'Channel: {channel.name} (ID: {channel.id})'] = r['target']
        keys = finder(current, filtered.keys())
        return [app_commands.Choice(name=k[:99], value=str(filtered[k])) for k in keys[:25]]

    @highlight.command(name='blocked')
    async def highlight_block_list(self, ctx: Context):
        """List your blocked users and channels"""
        query = '''SELECT type, target FROM hl_ignores WHERE id=$1;'''
        records = await self.bot.pool.fetch(query, ctx.author.id)
        if not records:
            return await ctx.send('You do not have any blocked users or channels', ephemeral=True)

        blocked_users = []
        blocked_channels = []
        for r in records:
            if r['type'] == 'user':
                blocked_users.append(f'<@{r["target"]}>')
            elif r['type'] == 'channel':
                blocked_channels.append(f'<#{r["target"]}>')

        e = discord.Embed(title='Highlight Ignores',
                          colour=discord.Colour.dark_blue())
        if blocked_users:
            e.add_field(name='Blocked Users', value='\n'.join(blocked_users) or 'None', inline=False)
        if blocked_channels:
            e.add_field(name='Blocked Channels', value='\n'.join(blocked_channels) or 'None', inline=False)
        e.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)

        if not ctx.interaction:
            await ctx.tick(True)
            await ctx.send(embed=e, delete_after=15)
        else:
            await ctx.send(embed=e, ephemeral=True)

    @highlight.group(name='clear')
    async def highlight_clear_group(self, ctx: Context):
        """Clear your highlight triggers or blocks"""
        await ctx.send_help(ctx.command)

    @highlight_clear_group.command(name='triggers')
    async def highlight_clear_triggers(self, ctx: Context):
        """Clear all your highlight triggers"""
        cont = await ctx.confirm_prompt('Are you sure you want to clear all your highlight triggers here? This cannot be undone.', ephemeral=True)
        if not cont:
            return await ctx.send('Cancelled', ephemeral=True)

        await self.delete_highlights(ctx.author.id, ctx.guild.id)
        if not ctx.interaction:
            await ctx.tick(True)
            await ctx.send('Successfully cleared all your highlight triggers', delete_after=7)
        else:
            await ctx.send(f'{await ctx.tick(reaction=False)} Successfully cleared all your highlight triggers', ephemeral=True)

    @highlight_clear_group.command(name='blocks')
    async def highlight_clear_blocks(self, ctx: Context):
        """Clear all your highlight blocks"""
        cont = await ctx.confirm_prompt('Are you sure you want to clear all your highlight blocks here? This cannot be undone.', ephemeral=True)
        if not cont:
            return await ctx.send('Cancelled', ephemeral=True)

        query = '''DELETE FROM hl_ignores WHERE id=$1;'''
        await self.bot.pool.execute(query, ctx.author.id)
        self.ignores.pop(ctx.author.id, None)
        if not ctx.interaction:
            await ctx.tick(True)
            await ctx.send('Successfully cleared all your highlight blocks', delete_after=7)
        else:
            await ctx.send(f'{await ctx.tick(reaction=False)} Successfully cleared all your highlight blocks', ephemeral=True)


async def setup(bot: SnowflakeBot):
    await bot.add_cog(Highlights(bot))
