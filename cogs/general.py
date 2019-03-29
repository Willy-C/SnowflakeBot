import discord
from discord.ext import commands
from jishaku.codeblocks import Codeblock, CodeblockConverter


class GeneralCog(commands.Cog, name='General Commands'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='eval', enabled=False)
    async def _eval(self, ctx, *, args: CodeblockConverter):
        """Evaluates python code in a single line or code block"""
        await ctx.invoke(self.bot.get_command("jsk py"), argument=args)

    @commands.command(aliases=['msg'])
    async def quote(self, ctx, user: discord.Member, *, message: commands.clean_content()):
        """Send a message as someone else"""
        hook = await ctx.channel.create_webhook(name=user.display_name)
        await hook.send(message, avatar_url=user.avatar_url_as(format='png'))
        await hook.delete()


def setup(bot):
    bot.add_cog(GeneralCog(bot))
