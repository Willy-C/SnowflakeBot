import discord
import traceback
from io import BytesIO
from discord.ext import commands
from datetime import datetime
from asyncpg import UniqueViolationError


class TrackerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.add_join_dates())
        self.bot.loop.create_task(self.add_avatar())
        self.bot.loop.create_task(self.add_names())

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
                    join_time = member.joined_at or datetime.utcnow()
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
            if (user.id, user.avatar) not in data and (user.id, user.default_avatar.name) not in data:
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
        join_time = member.joined_at or datetime.utcnow()
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
            join_time = member.joined_at or datetime.utcnow()
            try:
                await self.bot.pool.execute(query, member.guild.id, member.id, join_time)
            except Exception:
                traceback.print_exc()
            if member.nick:
                await self.log_nickname(member)
            if member.id not in ava_ids:
                await self.log_avatar(member)

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
            hash = user.avatar
            type = 'gif' if hash.startswith('a_') else 'png'
            file = discord.File(BytesIO(await user.avatar_url_as(static_format='png').read()),
                                filename=f'{hash}.{type}')
            wh = discord.utils.get(await self.bot.get_guild(557306479191916555).webhooks(),
                                   channel_id=703171905435467956)
            if wh is not None:
                try:
                    msg = await wh.send(content=user.id, file=file, wait=True, username=hash)
                except discord.HTTPException as e:
                    if 'Payload Too Large' in str(e):
                        file = discord.File(BytesIO(await user.avatar_url_as(format='png').read()),
                                            filename=f'{hash}.png')
                        msg = await wh.send(content=user.id, file=file, wait=True, username=hash)
            else:
                self.bot.get_channel(703171905435467956)
                msg = await self.bot.get_channel(703171905435467956).send(content=user.id, file=file)
            url = msg.attachments[0].url
            message_id = msg.id
        else:
            hash = user.default_avatar.name
            url = str(user.default_avatar_url)
            message_id = None
        query = '''INSERT INTO avatar_changes(id, hash, url, message, changed_at)
                   VALUES($1, $2, $3, $4, $5);'''
        await self.bot.pool.execute(query, user.id, hash, url, message_id, datetime.utcnow())


def setup(bot):
    bot.add_cog(TrackerCog(bot))
