import discord
from discord.ext import commands
from asyncpg import UniqueViolationError
from collections import defaultdict

from utils import valorantapi
from utils.converters import CaseInsensitiveMember
from utils.views import LoginView, _2FAView



class Valorant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._authclients = defaultdict(dict)

    def get_auth_for(self, user_id: int, username: str, password: str) -> valorantapi.VALORANTAuth:
        if username not in self._authclients[user_id]:
            self._authclients[user_id][username] = valorantapi.VALORANTAuth(username, password)

        return self._authclients[user_id][username]


    async def fetch_login(self, user_id: int):
        query = '''SELECT username, password, riotid 
                   FROM valcreds 
                   WHERE id = $1 AND private = FALSE'''
        records = await self.bot.pool.fetch(query, user_id)
        return records

    async def check_login(self, user_id: int):
        records = await self.fetch_login(user_id)
        if not records:
            return None

    async def wait_for_2fa(self, ctx, auth: valorantapi.VALORANTAuth, displayname: str = None):
        view = _2FAView(ctx=ctx)
        name = f'for `{displayname}`' if displayname else ''
        msg = await ctx.reply(f'Check your email and Click the button to submit 2fa code {name}', view=view)
        await view.wait()
        interaction = view.interaction
        _2fa_code = getattr(view.code, 'value', None)

        if _2fa_code is None:
            raise ValueError('No 2fa code found')

        auth._2fa_code = _2fa_code
        await msg.delete(delay=5)


    @commands.group(name='valorant', aliases=['val'], invoke_without_command=True, case_insensitive=True)
    async def valorant_commands(self, ctx):
        await ctx.send_help(ctx.command)

    @valorant_commands.command(name='shop', hidden=True, usage='')
    async def check_shop(self, ctx, user: CaseInsensitiveMember = None):
        user = user or ctx.author
        logins = await self.fetch_login(user.id)
        if not logins:
            return await ctx.reply('I am unable to find your login!\n'
                                   'Please make sure you saved your login with `%val login add`')

        for login in logins:
            username = login['username']
            password = login['password']
            display_name = login['riotid']

            async with valorantapi.VALORANTAuth(username, password) as auth:
                try:
                    skins = await auth.check_store()
                except valorantapi.MultiFactorCodeRequired:
                    await self.wait_for_2fa(ctx, auth, display_name)
                    skins = await auth.check_store()

                if not skins:
                    continue
                names = [s['displayName'] for s in skins]
                skin_names = "\n".join(names)

                icons = [s['displayIcon'] for s in skins]
                embeds = []
                for icon in icons:
                    e = discord.Embed(title='', url='https://playvalorant.com/en-us/')
                    e.set_image(url=icon)
                    e.set_footer(text='Click on image for full quality')
                    embeds.append(e)

                await ctx.send(f'Available skins for `{display_name}`:\n{skin_names}', embeds=embeds)

    @valorant_commands.group(name='login', invoke_without_command=True, case_insensitive=True)
    async def valorant_login_commands(self, ctx):
        await ctx.send_help(ctx.command)

    @valorant_login_commands.command(name='add')
    async def add_account(self, ctx):
        view = LoginView(ctx=ctx)
        msg = await ctx.reply('Click the button to start the login process', view=view)
        await view.wait()
        interaction = view.interaction
        username = getattr(view.username, 'value', None)
        password = getattr(view.password, 'value', None)

        if username is None or password is None:
            return await ctx.reply('Did not receive username and password')

        async with valorantapi.VALORANTAuth(username, password) as auth:
            try:
                riotid = await auth.get_username()
            except valorantapi.MultiFactorCodeRequired:
                await self.wait_for_2fa(ctx, auth)
                riotid = await auth.get_username()
                # await ctx.tick(False)
                # await interaction.followup.send('Sorry, you must 2-factor authentication disabled for me to work.')
                # return
            except KeyError:
                await ctx.tick(False)
                await interaction.followup.send('I am unable to authenticate with the given credentials.\n'
                                                'Please make sure they are correct and try again')
                return
            finally:
                await msg.delete(delay=20)

        query = '''INSERT INTO valcreds(id, username, password, riotid)
                   VALUES ($1, $2, $3, $4)'''
        try:
            await self.bot.pool.execute(query, ctx.author.id, username, password, riotid)
        except UniqueViolationError:
            await ctx.tick(False)
            await interaction.followup.send(f'Error: Credentials for username `{username}` already exists!\n'
                                            f'If you want to change your password, please use `%val login delete [username] and readd it with `%val login add``')
        else:
            await ctx.tick()
            await interaction.followup.send(f'Added credentials for Username: {username} (Riot ID: {riotid})')
        finally:
            await msg.delete(delay=10)

    @valorant_login_commands.command(name='remove', aliases=['delete'])
    async def delete_account(self, ctx, username):
        query = '''DELETE FROM valcreds WHERE id = $1 AND username = $2;'''
        status = await self.bot.pool.execute(query, ctx.author.id, username)
        if status == 'DELETE 0':
            await ctx.tick(False)
            return await ctx.reply('I am unable to delete that username')
        else:
            await ctx.tick()
            return await ctx.reply('Successfully deleted your credentials')

    @valorant_login_commands.command(name='list')
    async def list_accounts(self, ctx):
        query = '''SELECT riotid FROM valcreds where id = $1;'''
        records = await self.bot.pool.fetch(query, ctx.author.id)
        names = [record['riotid'] for record in records]
        fmt = ', '.join(names)
        await ctx.reply(f'You have {len(names)} account(s) saved: {fmt}', delete_after=5)


def setup(bot):
    bot.add_cog(Valorant(bot))
