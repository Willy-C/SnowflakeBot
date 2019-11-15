import discord
from discord.ext import commands

GUILD_ID = 567520394215686144

FLOATER_ROLE_ID = 567539820545572865

class ViCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != GUILD_ID:
            return

        floater = member.guild.get_role(FLOATER_ROLE_ID)
        if floater is None: # Could not find role for some reason
            return

        try:
            await member.add_roles(floater)
        except discord.HTTPException:
            pass


def setup(bot):
    bot.add_cog(ViCog(bot))
