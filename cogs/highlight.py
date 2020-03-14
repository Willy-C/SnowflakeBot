import discord
from discord.ext import commands

import re
import random
from datetime import datetime, timedelta
from asyncio import TimeoutError
from typing import Union
from asyncpg import UniqueViolationError

from utils.global_utils import confirm_prompt


class HighlightCog(commands.Cog, name='Highlight'):

    def __init__(self, bot):
        self.bot = bot
        self.highlights = {}
        self.bot.loop.create_task(self.populate_cache())
        self.bot.loop.create_task(self.get_data())

    async def get_data(self):
        mention_query = '''SELECT * FROM mentions'''
        records = await self.bot.pool.fetch(mention_query)
        self.mentions = [record['user'] for record in records]

        ignore_query = '''SELECT * FROM hlignores;'''
        records = await self.bot.pool.fetch(ignore_query)
        collect_ignores = {}
        for record in records:
            uid = record['user']
            ignores = collect_ignores.setdefault(uid, {})
            type = record['type']
            ignores.setdefault(type+'s', []).append(record['id'])
        self.ignores = collect_ignores


    @staticmethod
    def create_regex(words):
        return re.compile(r'\b(?:' + '|'.join(map(re.escape, words)) + r')s?\b', re.IGNORECASE)

    async def update_regex(self, ctx, guild_id=None):
        query = '''SELECT word
                   FROM highlights
                   WHERE guild = $1
                   AND "user" = $2;'''
        gid = guild_id or ctx.guild.id
        records = await self.bot.pool.fetch(query, gid, ctx.author.id,)
        words = [record['word'] for record in records]
        guild_hl = self.highlights.setdefault(gid, {})
        guild_hl[ctx.author.id] = self.create_regex(words)

    def create_guild_regex(self, records):
        guild_regex = {}
        collect_words = {}
        for record in records:
            uid = record.get('user')
            if uid in collect_words:
                collect_words[uid].append(record.get('word'))
            else:
                collect_words[uid] = [record.get('word')]

        for user, words in collect_words.items():
            guild_regex[user] = self.create_regex(words)
        return guild_regex

    async def populate_cache(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            query = '''SELECT "user", word
                       FROM highlights
                       WHERE guild = $1;'''
            records = await self.bot.pool.fetch(query, guild.id)
            if not records:
                continue
            self.highlights[guild.id] = self.create_guild_regex(records)

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
        trigger = re.compile(r'\b' + word + r's?\b', re.IGNORECASE)
        if any([trigger.search(msg.content) and msg.author.id not in users_to_ignore for msg in recent_msgs]):  # Recently highlighted
            return True
        return False

    async def get_msg_context(self, message, member_id, word, is_mention=False):
        now = datetime.utcnow()
        prev_msgs = await message.channel.history(after=(now-timedelta(minutes=5))).flatten()  # Grabs all messages from the last 5 minutes
        msg_context = []
        recent_msgs = [msg for msg in prev_msgs[:-1] if (now - msg.created_at).seconds <= 60]  # List of messages from last 60 seconds

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
        if message.author.bot or message.guild is None or message.webhook_id is not None:
            return
        if message.guild.id in self.highlights:
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
    async def add(self, ctx, keyword, guild_id: int = None):
        """Add a highlight keyword for the current server"""
        guild = self.bot.get_guild(guild_id) or ctx.guild
        if guild is None:
            return await ctx.send('Please use this command in a server or specify a server ID!')
        if ctx.guild is not None:
            delete_after = 10
        else:
            delete_after = None
        key = keyword.lower()
        if len(key) < 3:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            return await ctx.send('Keywords must be at least 3 characters!')
        try:
            add_query = '''INSERT INTO highlights(guild, "user", word)
                           VALUES ($1, $2, $3);'''
            await self.bot.pool.execute(add_query, guild.id, ctx.author.id, keyword)
        except UniqueViolationError:
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            return await ctx.send('You already have this word added!', delete_after=delete_after)
        else:
            await self.update_regex(ctx, guild.id)
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
            await ctx.send(f'Successfully added highlight key: `{key}` for `{guild}`', delete_after=delete_after)

    @highlight.command()
    async def remove(self, ctx, keyword, guild_id: int = None):
        """Remove a highlight keyword for the current server"""
        guild = self.bot.get_guild(guild_id) or ctx.guild
        if guild is None:
            return await ctx.send('Please use this command in a server or specify a server ID!')
        if ctx.guild is not None:
            delete_after = 10
        else:
            delete_after = None

        key = keyword.lower()
        remove_query = '''DELETE FROM highlights
                          WHERE guild = $1
                          AND "user" = $2
                          AND word = $3'''
        result = await self.bot.pool.execute(remove_query, guild.id, ctx.author.id, keyword)
        if result == 'DELETE 0':
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            return await ctx.send('Sorry, you do not seem to have this word added', delete_after=delete_after)

        else:
            await self.update_regex(ctx, guild.id)
            query = '''SELECT DISTINCT "user" 
                       FROM highlights
                       WHERE guild = $1;'''
            records = await self.bot.pool.fetch(query, guild.id)

            guild_records = [record['user'] for record in records]
            if ctx.author.id not in guild_records:
                del self.highlights[guild.id][ctx.author.id]
                if not self.highlights[guild.id]:
                    del self.highlights[guild.id]
        await ctx.message.add_reaction('\U00002705')  # React with checkmark
        await ctx.send(f'Successfully removed  highlight key: `{key}` for `{guild}`', delete_after=delete_after)

    @highlight.command(name='import')
    @commands.guild_only()
    async def _import(self, ctx, *, guild: Union[int, str]):
        """Import your highlight words from another server."""
        g = self.bot.get_guild(guild)
        if g is None:
            g = discord.utils.get(self.bot.guilds, name=str(guild))
        if g is not None:
            query = '''SELECT word
                       FROM highlights
                       WHERE guild = $1
                       AND "user" = $2;'''
            records = await self.bot.pool.fetch(query, g.id, ctx.author.id)
            words = [(ctx.guild.id, ctx.author.id, record["word"]) for record in records]
            insert = '''INSERT INTO highlights(guild, "user", word)
                        VALUES ($1, $2, $3);'''
            await self.bot.pool.executemany(insert, words)
            await self.update_regex(ctx)
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
            await ctx.send(f'Imported your highlights from `{g}`', delete_after=10)
        else:
            await ctx.send('Unable to find server with that name or ID', delete_after=10)
            await ctx.message.add_reaction('<:redTick:602811779474522113>')

    @highlight.command()
    async def list(self, ctx):
        """List your highlight words for the current guild
        If used in DM, all words from all guilds will be given"""
        delete_after = 15
        if ctx.guild is None:
            query = '''SELECT guild, word
                       FROM highlights
                       WHERE "user" = $1
                       ORDER BY word'''
            records = await self.bot.pool.fetch(query, ctx.author.id)
            all_hl = []
            collect_words = {}
            for record in records:
                gid = record['guild']
                if gid in collect_words:
                    collect_words[gid].append(record['word'])
                else:
                    collect_words[gid] = [record.get('word')]
            for guild, words in collect_words.items():
                all_hl.append(f'**__{self.bot.get_guild(guild)}__**')
                all_hl.extend(words)
            words = '\n'.join(all_hl)
            delete_after = None

        else:
            query = '''SELECT word
                       FROM highlights
                       WHERE guild = $1
                       AND "user" = $2
                       ORDER BY word'''
            records = await self.bot.pool.fetch(query, ctx.guild.id, ctx.author.id)
            if records:
                words = '\n'.join([record['word'] for record in records])
            else:
                words = 'You do not have any highlight words here'
        e = discord.Embed(color=discord.Color.dark_orange(),
                          title=f'Highlights for {(ctx.guild or ctx.author)}',
                          description=words)
        e.add_field(name='Mentions', value="ON" if ctx.author.id in self.mentions else "OFF")
        e.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

        await ctx.message.add_reaction('\U00002705')  # React with checkmark
        await ctx.send(embed=e, delete_after=delete_after)

    @highlight.command()
    async def mention(self, ctx):
        """Toggle highlight for mentions"""
        if ctx.guild is not None:
            delete_after = 10
        else:
            delete_after = None

        query = '''DELETE FROM mentions
                    WHERE "user" = $1'''

        deleted = await self.bot.pool.execute(query, ctx.author.id)
        if deleted == 'DELETE 0':
            toggle = '''INSERT INTO mentions VALUES($1)'''
            await ctx.send('You will now get a DM when I see you mentioned', delete_after=delete_after)
            await ctx.message.add_reaction('\U00002795')  # React with plus sign
            await self.bot.pool.execute(toggle, ctx.author.id)
        else:
            await ctx.send('You will no longer get a DM when I see you mentioned', delete_after=delete_after)
            await ctx.message.add_reaction('\U00002796')  # React with minus sign

    @highlight.command()
    async def clear(self, ctx, guild_id: int = None):
        """Clear all highlight words for the current guild
        Can pass in a guild id to specify a guild to clear from
        If used in DM with no guild specified, clears all words from all guilds
        Note: This will also disable highlight for mentions/pings"""
        if ctx.guild is None and guild_id is None:
            if not await confirm_prompt(ctx, 'Clear all highlight words from **every** server?'):
                return

            query = '''DELETE FROM highlights
                       WHERE "user" = $1'''
            await self.bot.pool.execute(query, ctx.author.id)

            to_del = []
            for guild in self.highlights:
                if ctx.author.id in self.highlights[guild]:
                    del self.highlights[guild][ctx.author.id]
                    if not self.highlights[guild]:
                        to_del.append(guild)

            for gid in to_del:
                del self.highlights[gid]
            await ctx.send(f'Cleared all of your highlight words')

        else:
            guild = self.bot.get_guild(guild_id) or ctx.guild
            if not await confirm_prompt(ctx, f'Clear all highlight words for `{guild}`?'):
                return
            query = '''DELETE FROM highlights
                       WHERE guild = $1
                       AND "user" = $2;'''
            await self.bot.pool.execute(query, guild.id, ctx.author.id)

            del self.highlights[ctx.guild.id][ctx.author.id]
            if not self.highlights[ctx.guild.id]:
                del self.highlights[ctx.guild.id]
            await ctx.send(f'Cleared all of your highlight words for `{ctx.guild}`', delete_after=7)

        if ctx.author.id in self.mentions:
            self.mentions.remove(ctx.author.id)
        await ctx.message.add_reaction('\U00002705')

    @highlight.command(name='ignore')
    async def toggle_ignore(self, ctx, target: Union[discord.User, discord.TextChannel, str]):
        """Toggle ignores for highlight
        Can enter a User, TextChannel via mention, ID or name"""
        if ctx.guild is not None:
            delete_after = 7
        else:
            delete_after = None
        ignores = self.ignores.setdefault(ctx.author.id, {})
        adding = False
        if isinstance(target, discord.User):
            users = ignores.setdefault('users', [])
            if target.id not in users:
                users.append(target.id)
                await ctx.send(f'Ignoring highlights from `{target}`', delete_after=delete_after)
                adding = 'user'
                await ctx.message.add_reaction('\U00002795')  # React with plus sign
            else:
                users.remove(target.id)
                await ctx.send(f'No longer ignoring highlights from `{target}`', delete_after=delete_after)
                if not ignores['users']:
                    del ignores['users']
                await ctx.message.add_reaction('\U00002796')  # React with minus sign
            await ctx.message.add_reaction('\U00002705')  # React with checkmark

        elif isinstance(target, discord.TextChannel):
            channels = ignores.setdefault('channels', [])
            if target.id not in channels:
                channels.append(target.id)
                await ctx.send(f'Ignoring highlights from `{target}`', delete_after=delete_after)
                adding = 'channel'
                await ctx.message.add_reaction('\U00002795')  # React with plus sign
            else:
                channels.remove(target.id)
                await ctx.send(f'No longer ignoring highlights from `{target}`!', delete_after=delete_after)
                if not ignores['channels']:
                    del ignores['channels']
                await ctx.message.add_reaction('\U00002796')  # React with minus sign
            await ctx.message.add_reaction('\U00002705')  # React with checkmark
        else:
            adding = None
            await ctx.message.add_reaction('<:redTick:602811779474522113>')
            await ctx.send('Unable to find target to ignore, please enter a users or a text channel', delete_after=delete_after)
        if not ignores:
            del self.ignores[ctx.author.id]

        if adding:
            query = '''INSERT INTO hlignores("user", id, type)
                       VALUES ($1, $2, $3);'''
            await self.bot.pool.execute(query, ctx.author.id, target.id, adding)
        elif adding is not None:
            delete_query = '''DELETE FROM hlignores
                              WHERE "user" = $1 
                              AND id = $2;'''
            await self.bot.pool.execute(delete_query, ctx.author.id, target.id)

    @highlight.command(name='ignores', aliases=['listignores'])
    async def list_ignores(self, ctx):
        """List your current ignores"""
        if ctx.guild is not None:
            delete_after = 15
        else:
            delete_after = None
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
            await ctx.send(embed=e, delete_after=delete_after)
        else:
            await ctx.send('You do not have ignores set!', delete_after=delete_after)
        await ctx.message.add_reaction('\U00002705')  # React with checkmark


def setup(bot):
    bot.add_cog(HighlightCog(bot))
