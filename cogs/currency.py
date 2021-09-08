import discord
from discord.ext import commands
import datetime

from utils.converters import CaseInsensitiveMember, CurrencyConverter


class Currency(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=error.retry_after)
            await ctx.reply(f'You are on cooldown! You can use this command again: {discord.utils.format_dt(dt, "R")}')
            ctx.local_handled = True

    async def _increase_money(self, user: discord.User, amount: float):
        query = '''INSERT INTO currency(id, money)
                   VALUES($1, $2) ON CONFLICT (id) DO UPDATE
                   SET money = currency.money + $2'''
        await self.bot.pool.execute(query, user.id, amount)

    async def _set_money(self, user: discord.User, amount: float):
        query = '''INSERT INTO currency(id, money)
                   VALUES($1, $2) ON CONFLICT (id) DO UPDATE
                   SET money = $2'''
        await self.bot.pool.execute(query, user.id, amount)

    async def get_balance(self, user: discord.User) -> float:
        query = '''SELECT money FROM currency WHERE id = $1'''
        record = await self.bot.pool.fetchrow(query, user.id)
        if record is None:
            return 0
        else:
            return record['money']

    @commands.group(name='money', invoke_without_command=True, case_insensitive=True)
    async def _currency(self, ctx):
        await self.get_money(ctx)

    @_currency.command(name='add', aliases=['give'])
    @commands.is_owner()
    async def add_money(self, ctx, user: CaseInsensitiveMember, amount: CurrencyConverter):
        await self._increase_money(user, amount)
        await ctx.tick()

    @_currency.command(name='remove', aliases=['take'])
    @commands.is_owner()
    async def remove_money(self, ctx, user: CaseInsensitiveMember, amount: CurrencyConverter):
        await self._increase_money(user, -amount)
        await ctx.tick()

    @_currency.command(name='set')
    @commands.is_owner()
    async def set_money(self, ctx, user: CaseInsensitiveMember, amount: CurrencyConverter):
        await self._set_money(user, amount)
        await ctx.tick()

    @_currency.command(name='show')
    async def get_money(self, ctx, user: CaseInsensitiveMember=None):
        user = user or ctx.author
        amount = await self.get_balance(user)
        _user = 'You have' if user == ctx.author else f'{user.mention} has'
        await ctx.reply(f'{_user} ${amount:.2f}',
                        allowed_mentions=discord.AllowedMentions.none())

    @_currency.command(name='restart', aliases=['reset', 'start'])
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def restart_money(self, ctx):
        amount = await self.get_balance(ctx.author)
        if amount:
            if not await ctx.confirm_prompt(f'Are you sure want to reset your money back to $1000? (Balance: ${amount:2f})\n'
                                            f'This command can only be used once every 30 minutes'):
                self.restart_money.reset_cooldown(ctx)
                return
        await self._set_money(ctx.author, 1000)
        await ctx.reply('You now have $1000')
        await ctx.tick()

    @_currency.command(name='send')
    async def send_money(self, ctx, user: CaseInsensitiveMember, amount: CurrencyConverter):
        if user == ctx.author:
            await ctx.reply('You cannot send money to yourself')
            return
        balance = await self.get_balance(ctx.author)
        if amount > balance:
            return await ctx.reply(f'You don\'t have enough money to send. (Balance: ${balance:.2f})')
        await self._increase_money(ctx.author, -amount)
        await self._increase_money(user, amount)
        await ctx.reply(f'Sent ${amount} to {user.mention}')
        await ctx.tick()

    @commands.command(name='balance', aliases=['bal'])
    async def _get_user_balance(self, ctx, user: CaseInsensitiveMember=None):
        await self.get_money(ctx, user=user)


def setup(bot):
    bot.add_cog(Currency(bot))
