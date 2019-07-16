import discord
from discord.ext import commands

import time

from global_utils import copy_context


class MetaCog(commands.Cog, name='Metautil'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='debug', aliases=['dbg', 'timeit', 'time'])
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

        return await ctx.send(f'Command `{alt_ctx.command.qualified_name}` finished in {end - start:.3f}s.')

    @commands.command(brief='Checks latency to Discord.')
    async def ping(self, ctx: commands.Context):
        start = time.perf_counter()
        msg = await ctx.send('mew')
        end = time.perf_counter()
        await msg.edit(content=f'(WS) Latency: `{self.bot.latency*1000:.2f}ms`\n'
                               f'Response time: `{(end - start)*1000:.2f}ms`')

    @commands.command()
    async def invite(self, ctx):
        """
        The invite link to add me to your server.
        """
        e = discord.Embed(title='Invite me to your server!',
                          color=discord.Colour(0x00FFFF),
                          description=f'[Click here to invite me](https://discordapp.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot)')
        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(MetaCog(bot))
