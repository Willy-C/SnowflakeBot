import asyncio
import logging
import datetime
from typing import List, Optional
from collections import defaultdict

import discord
from discord.ext import commands, tasks
from asyncpg import UniqueViolationError

from utils.valorantapi import VALORANTAuth, get_closest_skin, update_skin_data
from utils.converters import CaseInsensitiveMember
from utils.views import LoginView, _2FAView
from utils.errors import MultiFactorCodeRequired, InvalidCredentials
from utils.global_utils import bright_color


log = logging.getLogger(__name__)


class Valorant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._authclients: dict[int, dict[str, VALORANTAuth]] = defaultdict(dict) # UserID: {PUUID: AuthClient}
        bot.loop.create_task(self.load_cog())
        self._shop_cache:  dict[int, dict[str, List[dict]]] = defaultdict(dict) # UserID: {PUUID: [skin dicts]}
        self.check_daily_shop.start()
        self._updated = asyncio.Event()
        self._updated.set()
        self._last_update: Optional[datetime.datetime] = None

    async def cog_command_error(self, ctx, error) -> None:
        error = getattr(error, 'original', error)
        if isinstance(error, MultiFactorCodeRequired):
            ctx.local_handled = True
            authclient = error.auth_client
            await self.wait_for_2fa(ctx, authclient)
            await authclient.authenticate_from_2fa()
            await ctx.reply(f'Successfully authenticated, please try your request again.', delete_after=5)

        elif isinstance(error, InvalidCredentials):
            ctx.local_handled = True
            await ctx.reply('Your credentials seem to be invalid', delete_after=5)

    def cog_unload(self) -> None:
        self.refresh_cookies.cancel()
        self.check_daily_shop.cancel()
        for user in self._authclients.values():
            for client in user.values():
                self.bot.loop.create_task(client.close())

    @tasks.loop(hours=672) # 28 days
    async def refresh_cookies(self):
        if self.refresh_cookies.current_loop == 0:
            return
        for user in self._authclients.values():
            for client in user.values():
                await client.reauthenticate()
                client.update_headers()

    async def load_cog(self):
        query = '''SELECT * FROM valcreds;'''
        records = await self.bot.pool.fetch(query)
        for r in records:
            user_id = r['id']
            puuid = r['puuid']
            self._authclients[user_id][puuid] = VALORANTAuth.from_record(r)
        self.refresh_cookies.start()

    @commands.group(name='valorant', aliases=['val'], invoke_without_command=True, case_insensitive=True)
    async def valorant_commands(self, ctx):
        """VALORANT related commands"""
        await ctx.send_help(ctx.command)

    @valorant_commands.command(name='login')
    async def add_account(self, ctx):
        """Add an account"""
        view = LoginView(ctx=ctx)
        msg = await ctx.reply('Click the button to start the login process', view=view)
        await view.wait()
        interaction = view.interaction
        username = getattr(view.username, 'value', None)
        password = getattr(view.password, 'value', None)

        if username is None or password is None:
            await ctx.reply('Did not receive username and password')
            try:
                await msg.delete()
            except discord.HTTPException:
                pass
            return

        authclient = VALORANTAuth(username=username, password=password)
        try:
            await authclient.authenticate_from_password()
        except MultiFactorCodeRequired:
            await self.wait_for_2fa(ctx, authclient)
            await authclient.authenticate_from_2fa()

        async with authclient as auth:
            try:
                riotid = await auth.get_username()
                puuid = auth.puuid
            except KeyError:
                await ctx.tick(False)
                await interaction.followup.send('I am unable to authenticate with the given credentials.\n'
                                                'Please make sure they are correct and try again')
                return
            finally:
                await msg.delete(delay=20)

        query = '''INSERT INTO valcreds(id, username, password, puuid, riotid)
                   VALUES ($1, $2, $3, $4, $5)'''
        try:
            await self.bot.pool.execute(query, ctx.author.id, username, password, puuid, riotid)
        except UniqueViolationError:
            await ctx.tick(False)
            await interaction.followup.send(f'Error: Credentials for username `{username}` already exists!\n'
                                            f'If you want to change your password, please use `%val login delete [username] and readd it with `%val login``')
        else:
            await ctx.tick()
            await interaction.followup.send(f'Added credentials for Username: {username} (Riot ID: {riotid})')
            self._authclients[ctx.author.id][puuid] = authclient
        finally:
            await msg.delete(delay=10)


    async def wait_for_2fa(self, ctx, auth: VALORANTAuth, displayname: str = None):
        view = _2FAView(ctx=ctx)
        name = f'for `{displayname}`' if displayname else ''
        msg = await ctx.reply(f'Seems like you have 2FA Enabled! Please check your email and Click the button to submit 2fa code {name}', view=view)
        await view.wait()
        # interaction = view.interaction
        _2fa_code = getattr(view.code, 'value', None)

        if _2fa_code is None:
            raise ValueError('No 2fa code found')

        auth._2fa_code = _2fa_code
        await msg.delete(delay=5)

    @valorant_commands.command(name='remove', aliases=['delete'])
    async def delete_account(self, ctx, username):
        """Delete an account"""
        query = '''DELETE FROM valcreds WHERE id = $1 AND username = $2;'''
        status = await self.bot.pool.execute(query, ctx.author.id, username)
        if status == 'DELETE 0':
            await ctx.tick(False)
            return await ctx.reply('I am unable to delete that username')
        else:
            await ctx.tick()
            return await ctx.reply('Successfully deleted your credentials')

    @valorant_commands.command(name='list')
    async def list_accounts(self, ctx):
        """List your saved accounts"""
        query = '''SELECT riotid FROM valcreds where id = $1;'''
        records = await self.bot.pool.fetch(query, ctx.author.id)
        names = [record['riotid'] for record in records]
        fmt = ', '.join(names)
        await ctx.reply(f'You have {len(names)} account(s) saved: {fmt}', delete_after=5)

    @valorant_commands.command(name='shop', usage='')
    async def check_shop(self, ctx, user: CaseInsensitiveMember = None):
        """Check your current daily shop items"""
        user = user or ctx.author
        if user.id not in self._authclients:
            return await ctx.reply('I am unable to find your account!\n'
                                   'Please make sure you saved your login with `%val login`')

        query = '''SELECT puuid, riotid FROM valcreds where id = $1;'''
        records = await self.bot.pool.fetch(query, user.id)
        riotids = {r['puuid']: r['riotid'] for r in records}

        if not self._updated.is_set():
            msg = await ctx.send('Currently checking daily shops. Please stand by...')
            async with ctx.typing():
                await self._updated.wait()
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass

        clients = self._authclients[user.id]
        cache = self._shop_cache[user.id]
        for puuid, client in clients.items():
            if puuid in cache and cache[puuid]:
                skins = cache[puuid]
            else:
                async with client as auth:
                    skins = await auth.check_store()
                    cache[puuid] = skins
            riotid = riotids[puuid]
            names = [s['displayName'] for s in skins]
            # skin_names = "\n".join(names)

            icons = [s['displayIcon'] for s in skins]
            embeds = []
            for name, icon in zip(names, icons):
                e = discord.Embed(title=name)
                e.set_image(url=icon)
                embeds.append(e)

            await ctx.send(f'Available skins for `{riotid}`:', embeds=embeds)

    async def correct_skin_name(self, ctx, name):
        skin = await get_closest_skin(name)
        if not skin:
            await ctx.reply(f'I am unable to find a skin matching {name}')
            return
        if skin[0].lower() != name.lower():
            do_correct = await ctx.confirm_prompt(f'Did you mean `{skin[0]}`?',
                                                  timeout=15)
            if not do_correct:
                return
        return skin[0]

    @valorant_commands.command(name='watch')
    async def add_skin_watch(self, ctx, *, name):
        """Add skin to watch for"""
        name = await self.correct_skin_name(ctx, name)
        if not name:
            return

        query = '''INSERT INTO valskinwatch(id, skin)
                   VALUES($1, $2);'''
        try:
            await self.bot.pool.execute(query, ctx.author.id, name)
        except UniqueViolationError:
            await ctx.tick(False)
            return await ctx.reply(f'You are already watching for `{name}`')
        else:
            await ctx.tick()
            await ctx.reply(f'You are now watching for `{name}`')
    #

    @valorant_commands.command(name='unwatch')
    async def remove_skin_watch(self, ctx, *, name):
        """Remove skin to watch for"""
        name = await self.correct_skin_name(ctx, name)
        if not name:
            return

        query = '''DELETE FROM valskinwatch
                   WHERE id=$1 AND skin=$2;'''
        status = await self.bot.pool.execute(query, ctx.author.id, name)
        if status == 'DELETE 0':
            await ctx.tick(False)
            return await ctx.reply('I am unable to delete that skin')
        else:
            await ctx.tick()
            return await ctx.reply(f'Successfully deleted watch for {name}')

    @valorant_commands.command(name='watchlist', usage='')
    async def list_skin_watch(self, ctx, *, member: CaseInsensitiveMember=None):
        """List skins you are watching for"""
        member = member or ctx.author
        query = '''SELECT skin FROM valskinwatch WHERE id = $1;'''
        records = await self.bot.pool.fetch(query, member.id)
        if not records:
            await ctx.reply('You are not watching for any skins!')
        else:
            fmt = '\n'.join([r['skin'] for r in records])
            await ctx.reply(f'Currently watching for:\n{fmt}')

    async def update_shop_cache(self):
        log.info('Caching shop items')
        self._updated.clear()
        self._shop_cache.clear()
        for user_id, d in self._authclients.items():
            for puuid, client in d.items():
                await asyncio.sleep(15)
                try:
                    async with client as auth:
                        skins = await auth.check_store()
                        if not skins:
                            continue
                        self._shop_cache[user_id][puuid] = skins
                        log.info(f'Cached skins for {user_id=} ({puuid=})')
                except MultiFactorCodeRequired:
                    log.warning(f'Unable to fetch skins for {user_id=} ({puuid=}): 2FA code requied')
                except InvalidCredentials:
                    log.warning(f'Unable to fetch skins for {user_id=} ({puuid=}): Invalid Credentials!')

        self._updated.set()

    @tasks.loop(time=datetime.time(hour=0, second=30))
    async def check_daily_shop(self):
        prev = self._last_update
        self._last_update = discord.utils.utcnow()
        if prev is not None and (discord.utils.utcnow() - prev).total_seconds() < 3600:
            return

        await self.update_shop_cache()

        query = '''SELECT * FROM valskinwatch;'''
        records = await self.bot.pool.fetch(query)
        to_watch = defaultdict(list)
        for record in records:
            user_id = record['id']
            to_watch[user_id].append(record['skin'])

        found = defaultdict(list)
        for user_id, d in self._shop_cache.items():
            for puuid, skins in d.items():
                for s in skins:
                    if s['displayName'] in to_watch[user_id]:
                        found[user_id].append(s['displayName'])
        if found:
            log.info(f'Daily shop check - Found!: {dict(found)}')
            fmt = [f'<@{user_id}>: {", ".join(skins)}' for user_id, skins in found.items()]
            ping_list = '\n'.join(fmt)
            out = f'Watched skins are found!\n{ping_list}'

            channel = self.bot.get_guild(709264610200649738).get_channel(709264610200649741)
            await channel.send(out)

            debug_channel = self.bot.get_guild(561073510127108096).get_channel(615470512579149824)
            await debug_channel.send(out)
        else:
            log.info(f'Daily shop check - no matches!: {to_watch=}')

        list_channel = self.bot.get_guild(709264610200649738).get_channel(996216829301239988)

        dt = discord.utils.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        dt_md = discord.utils.format_dt(dt, "D")
        divider = "="*30
        await list_channel.send(f'{divider}\n'
                                f'VALORANT Shops for {dt_md}\n'
                                f'{divider}')


        query = '''SELECT puuid, riotid FROM valcreds;'''
        records = await self.bot.pool.fetch(query)
        riotids = {r['puuid']: r['riotid'] for r in records}
        msg_dict = {}

        for user_id, d in self._shop_cache.items():
            for puuid, skins in d.items():
                riotid = riotids[puuid]
                names = [s['displayName'] for s in skins]
                # skin_names = "\n".join(names)

                icons = [s['displayIcon'] for s in skins]
                embeds = []
                for name, icon in zip(names, icons):
                    e = discord.Embed(title=name)
                    e.set_image(url=icon)
                    embeds.append(e)

                m = await list_channel.send(f'Available skins for `{riotid}`:', embeds=embeds)
                msg_dict[riotid] = m.jump_url

        list_embed = discord.Embed(color=bright_color(), description=dt_md)
        for rid, url in msg_dict.items():
            list_embed.add_field(name=rid, value=f'[Jump]({url})')

        await list_channel.send(embed=list_embed)

    @valorant_commands.command(name='nightmarket', aliases=['nm'], usage='')
    async def check_night_market(self, ctx, user: CaseInsensitiveMember = None):
        """Check your current night market items"""
        user = user or ctx.author
        if user.id not in self._authclients:
            return await ctx.reply('I am unable to find your account!\n'
                                   'Please make sure you saved your login with `%val login`')

        query = '''SELECT puuid, riotid FROM valcreds where id = $1;'''
        records = await self.bot.pool.fetch(query, user.id)
        riotids = {r['puuid']: r['riotid'] for r in records}

        if not self._updated.is_set():
            msg = await ctx.send('Currently checking daily shops. Please stand by...')
            async with ctx.typing():
                await self._updated.wait()
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass

        clients = self._authclients[user.id]
        for puuid, client in clients.items():
            async with client as auth:
                skins = await auth.check_night_market()
                if not skins:
                    await ctx.send('Unable to find night market skins.')
                    return

            riotid = riotids[puuid]
            names = [s['displayName'] for s in skins]
            # skin_names = "\n".join(names)

            icons = [s['displayIcon'] for s in skins]
            embeds = []
            for name, icon in zip(names, icons):
                e = discord.Embed(title=name)
                e.set_image(url=icon)
                embeds.append(e)

            await ctx.send(f'Nightmarket skins for `{riotid}`:', embeds=embeds)


async def setup(bot):
    await bot.add_cog(Valorant(bot))
