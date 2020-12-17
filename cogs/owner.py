import discord
from discord.ext import commands

import io
import asyncio
import datetime
import textwrap
import tabulate
import traceback
from collections import Counter
from typing import Optional, Union
from contextlib import redirect_stdout
from utils.errors import BlacklistedUser
from utils.converters import CaseInsensitiveUser, CaseInsensitiveMember, CachedUserID, CachedGuildID
from utils.global_utils import confirm_prompt, cleanup_code, copy_context, upload_hastebin, send_or_hastebin


class OwnerCog(commands.Cog, name='Owner'):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None
        bot.loop.create_task(self.get_blacklist())

    # Applies commands.is_owner() check for all methods in this cog
    async def cog_check(self, ctx):
        if not await ctx.bot.is_owner(ctx.author):
            raise commands.NotOwner('Only my owner can use this command.')
        return True

    @commands.command(name='load')
    async def load_cog(self, ctx, *, cog: str):
        """Loads a Module.
        Accepts dot path. e.g: cogs.owner"""

        try:
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'<:redTick:602811779474522113> {type(e).__name__} - {e}')
        else:
            await ctx.send(f'<:greenTick:602811779835494410> loaded {cog}')

    @commands.command(name='unload')
    async def unload_cog(self, ctx, *, cog: str):
        """ Unloads a Module.
        Accepts dot path. e.g: cogs.owner"""

        try:
            self.bot.unload_extension(cog)
        except Exception as e:
            await ctx.send(f'<:redTick:602811779474522113> {type(e).__name__} - {e}')
        else:
            await ctx.send(f'<:greenTick:602811779835494410> unloaded {cog}')

    @commands.command(name='reload')
    async def reload_cog(self, ctx, *, cog: str):
        """Reloads a Module.
        Accepts dot path e.g: cogs.owner"""
        try:
            try:
                self.bot.reload_extension(cog)
            except commands.ExtensionNotLoaded:
                self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'<:redTick:602811779474522113> {type(e).__name__} - {e}')
        else:
            await ctx.send(f'<:greenTick:602811779835494410> reloaded {cog}')

    def get_bot_member(self, ctx):
        if ctx.guild is None:
            botmember = self.bot.guilds[0].me
        else:
            botmember = ctx.me
        return botmember

    @commands.group(name='presence', invoke_without_command=True, case_insensitive=True)
    async def change_presence(self, ctx):
        await ctx.send_help(ctx.command)

    @change_presence.command(name='listen', aliases=['l'])
    async def listen(self, ctx, *, name):
        botmember = self.get_bot_member(ctx)
        status = botmember.status
        await self.bot.change_presence(activity=discord.Activity(name=name, type=discord.ActivityType.listening),
                                       status=status)
        await ctx.tick()

    @change_presence.command(name='playing', aliases=['play', 'p'])
    async def playing(self, ctx, *, name):
        botmember = self.get_bot_member(ctx)
        status = botmember.status
        await self.bot.change_presence(activity=discord.Game(name=name), status=status)
        await ctx.tick()

    @change_presence.command(name='streaming', aliases=['s'])
    async def streaming(self, ctx, name, url=None):
        botmember = self.get_bot_member(ctx)
        status = botmember.status
        url = url or 'https://www.twitch.tv/directory'
        await self.bot.change_presence(activity=discord.Streaming(name=name, url=url), status=status)
        await ctx.tick()

    @change_presence.command(name='watching', aliases=['w'])
    async def watching(self, ctx, *, name):
        botmember = self.get_bot_member(ctx)
        status = botmember.status
        await self.bot.change_presence(activity=discord.Activity(name=name, type=discord.ActivityType.watching),
                                       status=status)
        await ctx.tick()

    @change_presence.command(name='competing', aliases=['c'])
    async def competing(self, ctx, *, name):
        botmember = self.get_bot_member(ctx)
        status = botmember.status
        await self.bot.change_presence(activity=discord.Activity(name=name, type=discord.ActivityType.competing),
                                       status=status)
        await ctx.tick()

    @change_presence.command(name='status')
    async def status(self, ctx, status):
        statuses = {'online': discord.Status.online,
                    'offline': discord.Status.invisible,
                    'invis': discord.Status.invisible,
                    'invisible': discord.Status.invisible,
                    'idle': discord.Status.idle,
                    'dnd': discord.Status.dnd}
        status = status.lower()
        if status not in statuses:
            return await ctx.send(f'Not a valid status! Choose: [{", ".join(statuses.keys())}]')
        botmember = self.get_bot_member(ctx)
        activity = botmember.activity
        await self.bot.change_presence(status=statuses[status], activity=activity)
        await ctx.tick()

    @change_presence.command()
    async def clear(self, ctx):
        await self.bot.change_presence()
        await ctx.tick()

    @change_presence.command()
    async def reset(self, ctx):
        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name='you :)'))
        await ctx.tick()

    @commands.command(name='aeval')
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

    # Blacklist stuff

    async def get_blacklist(self):
        query = '''SELECT id
                   FROM blacklist
                   WHERE type='user';'''
        try:
            records = await self.bot.pool.fetch(query)
        except:
            self._blacklist = []
        else:
            self._blacklist = {record['id'] for record in records}

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        bots = sum([1 for m in guild.members if m.bot])
        bot_ratio = (bots / guild.member_count) * 100
        if guild.member_count > 25 and bot_ratio > 70:
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

            query = '''INSERT INTO blacklist(id, type, reason)
                       VALUES($1, 'guild', 'bot farm');'''
            await self.bot.execute(query)
            return
        query = '''SELECT id
                   FROM blacklist
                   WHERE id=$1 AND type='guild';'''
        record = await self.bot.pool.fetch(query, guild.id)
        if record:
            try:
                await guild.owner.send(f'This server is blacklisted, I will now leave.\n'
                                       f'If you believe this is a mistake please contact my owner.')
            except discord.Forbidden:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        return await channel.send(f'This server is blacklisted, I will now leave.\n'
                                                  f'If you believe this is a mistake please contact my owner.')
            finally:
                await guild.leave()

    @commands.command(aliases=['ignore'])
    async def blacklist(self, ctx, member: Union[CaseInsensitiveMember, CachedUserID], *, reason=None):
        query = '''INSERT INTO blacklist(id, type, reason)
                   VALUES($1, 'user', $2);'''
        await self.bot.pool.execute(query, member.id, reason)
        self._blacklist.add(member.id)
        await ctx.send(f'Ignoring {member}')
        await ctx.message.add_reaction('\U00002705')

    @commands.command(aliases=['unignore'])
    async def unblacklist(self, ctx, *, member_or_guild: Union[CaseInsensitiveMember, CachedUserID, CachedGuildID]):
        query = '''DELETE FROM blacklist
                   WHERE id = $1;'''
        await self.bot.pool.execute(query, member_or_guild.id)
        if isinstance(member_or_guild, (discord.User, discord.Member)):
            try:
                self._blacklist.remove(member_or_guild.id)
            except KeyError:
                pass
        await ctx.send(f'Unignoring {member_or_guild}')
        await ctx.message.add_reaction('\U00002705')

    @blacklist.error
    @unblacklist.error
    async def blacklist_error(self, ctx, error):
        if isinstance(error, commands.errors.BadUnionArgument):
            ctx.local_handled = True
            return await ctx.send('Unable to find that person/guild')

    async def bot_check(self, ctx):
        if ctx.author.id in self._blacklist:
            raise BlacklistedUser
        return True


def setup(bot):
    bot.add_cog(OwnerCog(bot))
