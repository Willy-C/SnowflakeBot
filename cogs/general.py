import discord
from discord.ext import commands

import time
import copy

from jishaku.codeblocks import Codeblock, CodeblockConverter
from global_utils import copy_context


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

    @commands.command(name="debug", aliases=["dbg"])
    async def _debug(self, ctx: commands.Context, *, command_string: str):
        """
        Run a command timing execution and catching exceptions.
        """
        alt_ctx = await copy_context(ctx, content=ctx.prefix + command_string)

        if alt_ctx.command is None:
            return await ctx.send(f'Command "{alt_ctx.invoked_with}" is not found')

        start = time.perf_counter()
        await alt_ctx.command.invoke(alt_ctx)
        end = time.perf_counter()

        return await ctx.send(f"Command `{alt_ctx.command.qualified_name}` finished in {end - start:.3f}s.")

    @commands.command(name='su')
    async def _su(self, ctx: commands.Context, target: discord.User, *, command_string: str):
        """
        Run a command as someone else.

        This will try to resolve to a Member, but will use a User if it can't find one.
        """

        if ctx.guild:
            # Try to upgrade to a Member instance
            # This used to be done by a Union converter, but doing it like this makes
            #  the command more compatible with chaining, e.g. `jsk in .. jsk su ..`
            target = ctx.guild.get_member(target.id) or target

        alt_ctx = await copy_context(ctx, author=target, content=ctx.prefix + command_string)

        if alt_ctx.command is None:
            return await ctx.send(f'Command "{alt_ctx.invoked_with}" is not found')

        return await alt_ctx.command.invoke(alt_ctx)

def setup(bot):
    bot.add_cog(GeneralCog(bot))
