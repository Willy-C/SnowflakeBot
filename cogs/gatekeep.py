import discord
from discord.ext import commands

GUILD_ID = 709264610200649738
VERIFIED_ROLE = 709265266709626881
GENERAL = 709264610200649741


class Gatekeep(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.get_verified_ids())

    async def get_verified_ids(self):
        query = '''SELECT id FROM gatekeep;'''
        records = await self.bot.pool.fetch(query)
        self.verified = {record.get('id') for record in records}

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != GUILD_ID:
            return

        if member.id in self.verified:
            role = discord.Object(id=VERIFIED_ROLE)
            try:
                await member.add_roles(role, reason='Automatic verification')
            except (discord.HTTPException, AttributeError) as err:
                pass


def setup(bot):
    bot.add_cog(Gatekeep(bot))
