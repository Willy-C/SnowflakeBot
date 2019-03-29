import discord
from discord.ext import commands


class FunCog(commands.Cog, name='For Fun Commands'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['msg'])
    async def quote(self, ctx, user: discord.Member, *, message: commands.clean_content()):
        """Send a message as someone else"""
        hook = await ctx.channel.create_webhook(name=user.display_name)
        await hook.send(message, avatar_url=user.avatar_url_as(format='png'))
        await hook.delete()


def setup(bot):
    bot.add_cog(FunCog(bot))
