import discord
from discord.ext import commands

import os
import time
import inspect
import datetime
import humanize

from utils.global_utils import copy_context


class MetaCog(commands.Cog, name='Meta'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='time', aliases=['timeit', 'debug'])
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
    async def ping(self, ctx):
        start = time.perf_counter()
        msg = await ctx.send('boop')
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

    @commands.command(name='allemojis', aliases=['allemotes'], hidden=True)
    async def all_guild_emojis(self, ctx, codepoint: bool = False):
        """
        Returns all emojis from every guild the bot can see
        Pass in True as a parameter to get codepoints"""
        paginator = commands.Paginator(suffix='', prefix='')

        for guild in sorted(self.bot.guilds, key=lambda g: g.name):

            if not guild.emojis:
                continue

            paginator.add_line(f'__**{guild.name}**__')
            emojis = sorted(guild.emojis, key=lambda e: e.name)

            if codepoint:
                for emoji in emojis:
                    paginator.add_line(f'{emoji} -- {emoji.name} -- `{emoji}`')
                paginator.add_line('')
            else:
                for emoji in emojis:
                    paginator.add_line(f'{emoji} -- {emoji.name}')
                paginator.add_line('')

        for page in paginator.pages:
            await ctx.send(page)

    @commands.command()
    async def uptime(self, ctx, simple: bool=True):
        """Returns the bot's uptime
        Pass in False to view more detailed time"""
        delta = (datetime.datetime.utcnow() - self.bot.starttime)

        if simple:
            return await ctx.send(f'Uptime: {humanize.naturaldelta(delta)}')

        seconds = abs(delta.seconds)
        d = delta.days
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int((seconds % 3600) % 60)
        await ctx.send(f'Uptime: {d}d {h}h {m}m {s}s')

    @commands.command(name='shared')
    async def shared_guilds(self, ctx, member: discord.Member=None):
        """Returns the number of guilds a member shares with the bot"""
        member = member or ctx.author
        count = 0
        for guild in self.bot.guilds:
            if guild.get_member(member.id):
                count += 1
        await ctx.send(f'I share {count} server{"s" if count > 1 else ""} with {member}')

    # Credits to Danny:
    @commands.command()
    async def source(self, ctx, *, command: str = None):
        """Displays  source code or for a specific command.

        To display the source code of a subcommand you can separate it by
        periods or space eg. highlight.mention or highlight mention
        """
        url = 'https://github.com/Willy-C/SnowflakeBot'
        branch = 'master'
        if command is None:
            return await ctx.send(url)

        if len(command.split()) == 1:
            cmd = self.bot.get_command(command.replace('.', ' '))
        else:
            cmd = self.bot.get_command(command)

        if cmd is None:
            return await ctx.send('Sorry. I am unable to find that command.')

        src = cmd.callback.__code__
        module = cmd.callback.__module__
        file = src.co_filename

        lines, firstlineno = inspect.getsourcelines(src)
        if not module.startswith('discord'):
            # not a built-in command
            location = os.path.relpath(file).replace('\\', '/')
        else:
            location = module.replace('.', '/') + '.py'
            url = 'https://github.com/Rapptz/discord.py'

        final_url = f'<{url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        await ctx.send(final_url)


def setup(bot):
    bot.add_cog(MetaCog(bot))
