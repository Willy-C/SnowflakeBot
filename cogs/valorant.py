import aiohttp
import discord
from discord.ext import commands, tasks
from asyncpg import UniqueViolationError
from collections import defaultdict

from utils.valorantapi import VALORANTAuth
from utils.converters import CaseInsensitiveMember
from utils.views import LoginView, _2FAView
from utils.errors import MultiFactorCodeRequired


class Valorant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._authclients: dict[int, dict[str, VALORANTAuth]] = defaultdict(dict)
        bot.loop.create_task(self.load_cog())


    def cog_unload(self) -> None:
        for user in self._authclients.values():
            for client in user.values():
                self.bot.loop.create_task(client.close())

    @tasks.loop(hours=672) # 28 days
    async def refresh_cookies(self):
        for user in self._authclients.values():
            for client in user.values():
                await client.reauthenticate()

    async def load_cog(self):
        query = '''SELECT * FROM valcreds;'''
        records = await self.bot.pool.fetch(query)
        for r in records:
            user_id = r['id']
            puuid = r['puuid']

            auth = VALORANTAuth.from_record(r)
            try:
                await auth.authenticate_from_cookies()
            except FileNotFoundError:
                await auth.authenticate_from_password()
            self._authclients[user_id][puuid] = auth
        self.refresh_cookies.start()

    @commands.group(name='valorant', aliases=['val'], invoke_without_command=True, case_insensitive=True)
    async def valorant_commands(self, ctx):
        await ctx.send_help(ctx.command)

    @valorant_commands.command(name='login')
    async def add_account(self, ctx):
        view = LoginView(ctx=ctx)
        msg = await ctx.reply('Click the button to start the login process', view=view)
        await view.wait()
        interaction = view.interaction
        username = getattr(view.username, 'value', None)
        password = getattr(view.password, 'value', None)

        if username is None or password is None:
            return await ctx.reply('Did not receive username and password')

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

    @valorant_commands.command(name='shop', hidden=True, usage='')
    async def check_shop(self, ctx, user: CaseInsensitiveMember = None):
        user = user or ctx.author
        if user.id not in self._authclients:
            return await ctx.reply('I am unable to find your account!\n'
                                   'Please make sure you saved your login with `%val login`')

        clients = self._authclients[user.id]
        for puuid, client in clients.items():
            async with client as auth:
                skins = await auth.check_store()
                riotid = await auth.get_username()
                names = [s['displayName'] for s in skins]
                skin_names = "\n".join(names)

                icons = [s['displayIcon'] for s in skins]
                embeds = []
                for name, icon in zip(names, icons):
                    e = discord.Embed(title=name)
                    e.set_image(url=icon)
                    embeds.append(e)

                await ctx.send(f'Available skins for `{riotid}`:', embeds=embeds)





def setup(bot):
    bot.add_cog(Valorant(bot))
