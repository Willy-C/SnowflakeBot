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

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        for member in guild.members:
            query = '''INSERT INTO first_join(guild, "user", time)
                   VALUES($1, $2, $3);'''
            join_time = member.joined_at or datetime.utcnow()
            try:
                await self.bot.pool.execute(query, member.guild.id, member.id, join_time)
            except Exception:
                traceback.print_exc()

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.name != after.name or before.discriminator != after.discriminator:
            query = '''INSERT INTO name_changes(id, name, discrim, changed_at)
                       VALUES($1, $2, $3, $4);'''
            await self.bot.pool.execute(query, after.id, after.name, after.discriminator, datetime.utcnow())
        if before.avatar != after.avatar:
            if after.avatar:
                hash = after.avatar
                type = 'gif' if hash.startswith('a_') else 'png'
                file = discord.File(BytesIO(await after.avatar_url_as(static_format='png').read()),
                                    filename=f'{hash}.{type}')
                wh = discord.utils.get(await self.bot.get_guild(557306479191916555).webhooks(),
                                       channel_id=703171905435467956)
                if wh is not None:
                    msg = await wh.send(content=hash, file=file, wait=True, username=after.id)
                else:
                    self.bot.get_channel(703171905435467956)
                    msg = await self.bot.get_channel(703171905435467956).send(content=hash, file=file)
                url = msg.attachments[0].url
                message_id = msg.id
            else:
                hash = after.default_avatar.name
                url = after.default_avatar_url
                message_id = None
            query = '''INSERT INTO avatar_changes(id, hash, url, message, changed_at)
                       VALUES($1, $2, $3, $4, $5);'''
            await self.bot.pool.execute(query, after.id, hash, url, message_id, datetime.utcnow())

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick and after.nick is not None:
            query = '''INSERT INTO nick_changes(id, guild, name, changed_at)
                       VALUES($1, $2, $3, $4);'''
            await self.bot.pool.execute(query, after.id, after.guild.id, after.nick, datetime.utcnow())


def setup(bot):
    bot.add_cog(TrackerCog(bot))
