import discord
from discord.ext import commands

import io
import asyncio
import datetime
import textwrap
import tabulate
import traceback
from collections import Counter
from typing import Optional
from contextlib import redirect_stdout
from utils.converters import CaseInsensitiveUser
from utils.global_utils import confirm_prompt, cleanup_code, copy_context, upload_hastebin, send_or_hastebin


class OwnerCog(commands.Cog, name='Owner'):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None

    # Applies commands.is_owner() check for all methods in this cog
    async def cog_check(self, ctx):
        if not await ctx.bot.is_owner(ctx.author):
            raise commands.NotOwner('Only my owner can use this command.')
        return True

    @commands.command(name='load')
    async def load_cog(self, ctx, *, cog: str):
        """Command which Loads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send(f'**`SUCCESS:`** loaded {cog}')

    @commands.command(name='unload')
    async def unload_cog(self, ctx, *, cog: str):
        """Command which Unloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.unload_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send(f'**`SUCCESS:`** unloaded {cog}')

    @commands.command(name='reload')
    async def reload_cog(self, ctx, *, cog: str):
        """Command which Reloads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.unload_extension(cog)
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send(f'**`SUCCESS`** reloaded {cog}')

    @commands.command(name='presence')
    async def change_presence(self, ctx, _type: str, *, name: Optional[str]):
        activities = {'L': discord.Activity(name=name, type=discord.ActivityType.listening),
                      'P': discord.Game(name=name),
                      'S': discord.Streaming(name=name, url='https://www.twitch.tv/directory'),
                      'W': discord.Activity(name=name, type=discord.ActivityType.watching),
                      'N': None,
                      'Default': discord.Activity(type=discord.ActivityType.listening, name='you :)')}

        statuses = {'Online': discord.Status.online,
                    'Offline': discord.Status.invisible,
                    'Idle': discord.Status.idle,
                    'DND': discord.Status.dnd}

        if _type in activities:
            await self.bot.change_presence(activity=activities[_type])
            await ctx.send('Changing my activity...')
        elif _type in statuses:
            await self.bot.change_presence(status=statuses[_type])
            await ctx.send('Changing my status...')
        else:
            await ctx.send('The specified presence cannot be found\n'
                           '```Activity: L | P | S | W | N | Default\n'
                           'Status: Online | Offline | Idle | DND```')

    @commands.command(name='eval')
    async def _eval(self, ctx, *, code: str):
        """Evaluates python code in a single line or code block"""
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())
        code = cleanup_code(code)
        stdout = io.StringIO()
        to_compile = f'async def func():\n{textwrap.indent(code, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await send_or_hastebin(ctx, content=value, code='py')
            else:
                self._last_result = ret
                await send_or_hastebin(ctx, f'{value}{ret}', code='py')

    @commands.command(name='as')
    async def _sudo(self, ctx, channel: Optional[discord.TextChannel], target: CaseInsensitiveUser, *, command: str):
        """
        Run a command as someone else.
        Try to resolve to a Member, if possible.
        """
        channel = channel or ctx.channel
        author = channel.guild.get_member(target.id) or target
        content = ctx.prefix + command
        new_ctx = await copy_context(ctx, author=author, channel=channel, content=content)
        if new_ctx.command is None:
            return await ctx.send(f'Command "{new_ctx.invoked_with}" is not found')

        await self.bot.invoke(new_ctx)

    @commands.command(name='sql')
    async def run_query(self, ctx, *, query):
        query = cleanup_code(query)

        is_multiple = query.count(';') > 1
        if is_multiple:
            # fetch does not support multiple statements
            method = self.bot.pool.execute
        else:
            method = self.bot.pool.fetch

        try:
            results = await method(query)
        except Exception:
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if is_multiple or rows == 0:
            return await ctx.send(f'```\n{results}```')
        headers = list(results[0].keys())
        values = [list(map(repr, v)) for v in results]
        table = tabulate.tabulate(values, tablefmt='psql', headers=headers)
        if len(table) > 1000:
            url = await upload_hastebin(ctx, table)
            return await ctx.send(f'Output too long, uploaded to hastebin instead: <{url}>')

        await ctx.send(f'```\n{table}```')

    @commands.command(name="shutdown")
    async def logout(self, ctx):
        """
        Logs out the bot.
        """
        if not await confirm_prompt(ctx, 'Shutdown?'):
            return
        await ctx.message.add_reaction('\U0001f620')
        await ctx.bot.logout()

    @commands.command(name='guilds')
    async def get_shared_guilds(self, ctx, user: discord.User):
        shared = []
        for guild in self.bot.guilds:
            if guild.get_member(user.id) is not None:
                shared.append(guild)
        fmt = "\n".join([f"{guild.name} - {guild.id}" for guild in shared])
        await ctx.send(f'```\nShared guilds with {user}\n{fmt}\n```')

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        bots = sum([1 for m in guild.members if m.bot])
        bot_ratio = (bots / guild.member_count) * 100
        if guild.member_count > 25 and bot_ratio > 50:
            try:
                await guild.owner.send(f'The server `{guild}` has been flagged as a bot collection/farm. I will now leave the server.\n'
                                       f'If you believe this is a mistake please contact my owner.')
            except discord.Forbidden:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        return await channel.send(f'The server `{guild}` has been flagged as a bot collection/farm. I will now leave the server.\n'
                                                  f'If you believe this is a mistake please contact my owner.')
            finally:
                await guild.leave()


def setup(bot):
    bot.add_cog(OwnerCog(bot))
