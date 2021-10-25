import asyncio
import traceback
from io import BytesIO
from collections import defaultdict
from datetime import datetime, timedelta

import discord
import humanize
from discord.ext import commands
from asyncpg import UniqueViolationError
from utils.global_utils import make_naive
from utils.converters import CaseInsensitiveVoiceChannel


class TrackerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.add_join_dates())
        self.bot.loop.create_task(self.add_avatar())
        self.bot.loop.create_task(self.add_names())
        self.vc_joins  = defaultdict(lambda: defaultdict(tuple))
        self.vc_leaves = defaultdict(lambda: defaultdict(tuple))
        # {guild: {channel: (member, datetime)}}
        self._default_avatar_names = {0: 'blurple',
                                      1: 'grey',
                                      2: 'green',
                                      3: 'orange',
                                      4: 'red'}

    async def add_join_dates(self):
        await self.bot.wait_until_ready()
        query = '''SELECT guild, "user" FROM first_join'''
        records = await self.bot.pool.fetch(query)
        data = {(record['guild'], record['user']) for record in records}
        new = 0
        for guild in self.bot.guilds:
            for member in guild.members:
                if (guild.id, member.id) not in data:
                    query = '''INSERT INTO first_join(guild, "user", time)
                           VALUES($1, $2, $3);'''
                    join_time = make_naive(member.joined_at or discord.utils.utcnow())
                    try:
                        await self.bot.pool.execute(query, member.guild.id, member.id, join_time)
                    except Exception:
                        traceback.print_exc()
                    else:
                        new += 1
        print(f'Added {new} new members\' join date')

    async def add_avatar(self):
        await self.bot.wait_until_ready()
        query = '''SELECT id, hash FROM avatar_changes'''
        records = await self.bot.pool.fetch(query)
        data = {(record['id'], record['hash']) for record in records}
        new = 0
        for user in self.bot.users:
            if not user.avatar:
                _hash = self._default_avatar_names.get(int(user.display_avatar.key))
                if _hash is None:
                    print(f'Unknown default avatar: {user.avatar.key} | {user.avatar}')
                    continue

            else:
                _hash = user.avatar.key

            if (user.id, _hash) not in data:
                await self.log_avatar(user)
                new += 1
        print(f'Added {new} untracked avatars')

    async def add_names(self):
        await self.bot.wait_until_ready()
        query = '''SELECT DISTINCT id FROM name_changes'''
        records = await self.bot.pool.fetch(query)
        data = {record['id'] for record in records}
        new = 0
        for user in self.bot.users:
            if user.id not in data:
                await self.log_username(user)
                new += 1
        print(f'Added {new} users\' names')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        query = '''INSERT INTO first_join(guild, "user", time)
                   VALUES($1, $2, $3);'''
        # In the rare case that it is None, default to utcnow
        join_time = make_naive(member.joined_at or discord.utils.utcnow())
        try:
            await self.bot.pool.execute(query, member.guild.id, member.id, join_time)
        except UniqueViolationError:
            pass
        check = '''SELECT * FROM name_changes WHERE id = $1;'''
        if await self.bot.pool.fetchrow(check, member.id) is None:
            await self.log_username(member)

        ava = '''SELECT id FROM avatar_changes WHERE id = $1'''
        if await self.bot.pool.fetchrow(ava, member.id) is None:
            await self.log_avatar(member)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        existing_ava = '''SELECT DISTINCT id FROM avatar_changes;'''
        records = await self.bot.pool.fetch(existing_ava)
        ava_ids = {record['id'] for record in records}

        for member in guild.members:
            query = '''INSERT INTO first_join(guild, "user", time)
                   VALUES($1, $2, $3);'''
            join_time = make_naive(member.joined_at or discord.utils.utcnow())
            try:
                await self.bot.pool.execute(query, member.guild.id, member.id, join_time)
            except Exception:
                traceback.print_exc()
            if member.nick:
                await self.log_nickname(member)
            if member.id not in ava_ids:
                await self.log_avatar(member)
                await asyncio.sleep(2)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick and after.nick is not None:
            await self.log_nickname(after)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.name != after.name or before.discriminator != after.discriminator:
            await self.log_username(after)
        if before.avatar != after.avatar:
            await self.log_avatar(after)

    async def log_nickname(self, member: discord.Member):
        query = '''INSERT INTO nick_changes(id, guild, name, changed_at)
                   VALUES($1, $2, $3, $4);'''
        await self.bot.pool.execute(query, member.id, member.guild.id, member.nick, datetime.utcnow())

    async def log_username(self, user: discord.User):
        query = '''INSERT INTO name_changes(id, name, discrim, changed_at)
                   VALUES($1, $2, $3, $4);'''
        await self.bot.pool.execute(query, user.id, user.name, user.discriminator, datetime.utcnow())

    async def log_avatar(self, user: discord.User):
        if user.avatar:
            _hash = user.avatar.key
            _type = 'gif' if _hash.startswith('a_') else 'png'
            file = discord.File(BytesIO(await user.avatar.with_static_format('png').read()),
                                filename=f'{_hash}.{_type}')
            wh = discord.utils.get(await self.bot.get_guild(557306479191916555).webhooks(),
                                   channel_id=703171905435467956)
            if wh is not None:
                try:
                    msg = await wh.send(content=user.id, file=file, wait=True, username=_hash)
                except discord.HTTPException as e:
                    if 'Payload Too Large' in str(e):
                        file = discord.File(BytesIO(await user.avatar.with_format('png').read()),
                                            filename=f'{_hash}.png')
                        msg = await wh.send(content=user.id, file=file, wait=True, username=_hash)
            else:
                self.bot.get_channel(703171905435467956)
                msg = await self.bot.get_channel(703171905435467956).send(content=user.id, file=file)
            url = msg.attachments[0].url
            message_id = msg.id
        else:
            _hash = self._default_avatar_names.get(int(user.display_avatar.key))
            if _hash is None:
                print(f'Unknown default avatar: {user.avatar.key} | {user.avatar}')
                return
            url = user.default_avatar.url
            message_id = None
        query = '''INSERT INTO avatar_changes(id, hash, url, message, changed_at)
                   VALUES($1, $2, $3, $4, $5);'''
        await self.bot.pool.execute(query, user.id, _hash, url, message_id, datetime.utcnow())
        return url

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        if before.channel is not None:
            self.vc_leaves[member.guild.id][before.channel.id] = (member, datetime.utcnow())
        if after.channel is not None:
            self.vc_joins[member.guild.id][after.channel.id] = (member, datetime.utcnow())

    @commands.command()
    async def who(self, ctx, *, voicechannel: CaseInsensitiveVoiceChannel = None):
        """See who last joined/left a voice channel
        Can also provide a user to see when they last joined/left
        Ex. `%who` - Will tell you who last joined/left your current voice channel
        Ex. `%who voice1` - Will tell you who last joined/left voice1 (Requires `Move Members` permission to view other voice channels
        Ex. `%who voice1 @Bob` - Will tell you when Bob last joined/left (Requires `Move Members` permission to view other voice channels"""
        if not ctx.guild and not voicechannel:
            return await ctx.send('You must specify a voice channel in DMs!')

        if voicechannel is None and not ctx.author.voice:
            return await ctx.send('You are not in a voice channel!')

        voicechannel = voicechannel or ctx.author.voice.channel
        author = voicechannel.guild.get_member(ctx.author.id) if not ctx.guild else ctx.author

        # We will disallow checking history of channel you are not in it or if you do not have move members perms
        if not author.guild_permissions.move_members and author.id != self.bot.owner_id:
            if author.voice is None or author.voice.channel != voicechannel:
                return await ctx.send('You are not in that voice channel!', delete_after=10)

        out = ''

        if self.vc_joins[voicechannel.guild.id][voicechannel.id]:
            last_join, join_time = self.vc_joins[voicechannel.guild.id][voicechannel.id]
            join_delta = datetime.utcnow() - join_time
            if join_delta > timedelta(minutes=15) and author.id != self.bot.owner_id:
                human_join = 'Over 15 minutes (Capped at 15)'
            else:
                human_join = humanize.naturaldelta(join_delta)
            out += f'Last person to join `{voicechannel}` was {last_join} - {human_join} ago\n'

        if self.vc_leaves[voicechannel.guild.id][voicechannel.id]:
            last_left, leave_time = self.vc_leaves[voicechannel.guild.id][voicechannel.id]
            leave_delta = datetime.utcnow() - leave_time
            if leave_delta > timedelta(minutes=15) and author.id != self.bot.owner_id:
                human_leave = 'Over 15 minutes (Capped at 15)'
            else:
                human_leave = humanize.naturaldelta(leave_delta)
            out += f'Last person to leave `{voicechannel}` was {last_left} - {human_leave} ago\n'

        delete = 15 if ctx.guild else None
        if out:
            await ctx.send(out, delete_after=delete)
            await ctx.message.add_reaction('<:greenTick:602811779835494410>')
        else:
            await ctx.send('Sorry, no logs found', delete_after=delete)
            await ctx.message.add_reaction('<:redTick:602811779474522113>')


def setup(bot):
    bot.add_cog(TrackerCog(bot))
