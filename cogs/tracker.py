import discord
from discord.ext import commands
from datetime import datetime
from asyncpg import UniqueViolationError


class TrackerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
