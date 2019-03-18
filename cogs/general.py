import discord
from discord.ext import commands
from jishaku.codeblocks import Codeblock, CodeblockConverter


class GeneralCog(commands.Cog, name='General Commands'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='eval')
    async def _eval(self, ctx, *, args: CodeblockConverter):
        """Evaluates python code in a single line or code block"""
        await ctx.invoke(self.bot.get_command("jishaku py"), argument=args)


def setup(bot):
    bot.add_cog(GeneralCog(bot))
