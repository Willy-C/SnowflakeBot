import discord
import traceback
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
        data = {(record['guild'],  record['user']) for record in records}
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
    async def on_member_join(self, member: discord.Member):
        query = '''INSERT INTO first_join(guild, "user", time)
                   VALUES($1, $2, $3);'''
        # In the rare case that it is None, default to utcnow
        join_time = member.joined_at or datetime.utcnow()
        try:
            await self.bot.pool.execute(query, member.guild.id, member.id, join_time)
        except UniqueViolationError:
            pass


def setup(bot):
    bot.add_cog(TrackerCog(bot))
