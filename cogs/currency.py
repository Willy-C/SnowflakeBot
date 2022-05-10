import datetime
from typing import Union, Literal

import discord
from discord.ext import commands
from tabulate import tabulate

from utils.context import Context
from utils.global_utils import bright_color
from utils.currency import increase_balance, decrease_balance, set_balance, get_balance
from utils.converters import CaseInsensitiveMember, CurrencyConverter, CachedUserID, MoneyConverter


class Currency(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._claim_cd = commands.CooldownMapping.from_cooldown(8, 14460, commands.BucketType.user)
        # self.pending_transactions = set()

    async def cog_command_error(self, ctx: Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=error.retry_after)
            await ctx.reply(f'You are on cooldown! You can use this command again: {discord.utils.format_dt(dt, "R")}')
            ctx.local_handled = True
        elif isinstance(error, commands.BadUnionArgument):
            if CurrencyConverter in error.converters:
                await ctx.reply('That is not a valid number')
            else:
                await ctx.reply('Unable to find that person')
            ctx.local_handled = True

        elif isinstance(error, commands.MaxConcurrencyReached):
            ctx.local_handled = True

    @commands.group(name='money', invoke_without_command=True, case_insensitive=True)
    async def _currency(self, ctx: Context):
        """See `%help money` for full list of subcommands"""
        await self.get_money(ctx)

    @_currency.command(name='add', aliases=['give'])
    @commands.is_owner()
    async def add_money(self, ctx: Context, user: Union[CaseInsensitiveMember, CachedUserID], amount: Union[CurrencyConverter, Literal['all']]):
        if isinstance(amount, float):
            await increase_balance(ctx, user, amount)
        elif amount == 'all':
            query = '''SELECT id from currency'''
            records = await self.bot.pool.fetch(query)
            count = 0
            for r in records:
                if ctx.guild is None or (member := ctx.guild.get_member(r['id'])) is not None:
                    await increase_balance(ctx, member, float(amount))
                    count += 1
            await ctx.reply(f'Added ${amount} to {count} members')
        await ctx.tick()

    @_currency.command(name='remove', aliases=['take'])
    @commands.is_owner()
    async def remove_money(self, ctx: Context, user: Union[CaseInsensitiveMember, CachedUserID], amount: MoneyConverter):
        if amount == 'all':
            await set_balance(ctx, user, 0)
            return
        elif amount == 'half':
            balance = await get_balance(ctx, user)
            amount = balance / 2

        await decrease_balance(ctx, user, amount)
        await ctx.tick()

    @_currency.command(name='set')
    @commands.is_owner()
    async def _set_money(self, ctx: Context, user: Union[CaseInsensitiveMember, CachedUserID], amount: CurrencyConverter):
        await set_balance(ctx, user, amount)
        await ctx.tick()

    @_currency.command(name='show')
    async def get_money(self, ctx: Context, user: CaseInsensitiveMember = None):
        user = user or ctx.author
        amount = await get_balance(ctx, user)
        _user = 'You have' if user == ctx.author else f'{user.mention} has'
        await ctx.reply(f'{_user} ${amount:,.2f}',
                        allowed_mentions=discord.AllowedMentions.none())

    @_currency.command(name='restart', aliases=['reset', 'start'])
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def restart_money(self, ctx: Context):
        if ctx.guild.id == 709264610200649738:
            if (discord.utils.utcnow() - ctx.author.created_at).total_seconds() < 2592000:
                return await ctx.reply('Sorry, your account is too new')
            elif (discord.utils.utcnow() - ctx.author.joined_at).total_seconds() < 604800:
                return await ctx.reply('Sorry, your account joined too recently')
            elif not ctx.author.avatar:
                return await ctx.reply('Sorry, you cannot use this')
        balance = await get_balance(ctx, ctx.author)
        if balance:
            if balance < 0:
                await increase_balance(ctx, ctx.author, 2000)
                await ctx.reply(f'Your balance increased by $2000. Current balance: ${balance:,.2f}')
                await ctx.tick()
                return
            if not await ctx.confirm_prompt(f'Are you sure want to reset your money back to $2000? (Balance: ${balance:,.2f})\n'
                                            f'This command can only be used once every 5 minutes'):
                self.restart_money.reset_cooldown(ctx)
                return
        await set_balance(ctx, ctx.author, 2000)
        await ctx.reply('You now have $2000')
        await ctx.tick()

    @_currency.command(name='send')
    @commands.max_concurrency(1, per=commands.BucketType.user, wait=True)
    async def send_money(self, ctx: Context, user: CaseInsensitiveMember, amount: MoneyConverter):
        if user == ctx.author:
            await ctx.reply('You cannot send money to yourself')
            return
        if user.bot:
            await ctx.reply(f'You cannot send money to {user.mention}', allowed_mentions=discord.AllowedMentions.none())
            return
        balance = await get_balance(ctx, ctx.author)

        if not isinstance(amount, float):
            if amount == 'all':
                amount = balance
            else:
                amount = balance / 2

        if amount > balance:
            return await ctx.reply(f'You don\'t have enough money to send. (Balance: ${balance:,.2f})')
        await decrease_balance(ctx, ctx.author, amount)
        target_balance = await get_balance(ctx, user)

        confirm_message = f'Are you sure you want to send ${amount} to {user.mention}?\n' \
                          f'{ctx.author.mention}: ${balance} → **${balance-amount}**\n' \
                          f'{user.mention}: ${target_balance} → **${target_balance+amount}**'
        if not await ctx.confirm_prompt(confirm_message):
            await increase_balance(ctx, ctx.author, amount)
            return
        await increase_balance(ctx, user, amount)
        await ctx.reply(f'Sent ${amount} to {user.mention}')
        await ctx.tick()

    @commands.command(name='balance', aliases=['bal'])
    async def _get_user_balance(self, ctx: Context, user: CaseInsensitiveMember = None):
        """Get balance of user. Leave user blank for yourself"""
        await self.get_money(ctx, user=user)

    @commands.command(name='leaderboard', aliases=['lb'], usage='')
    async def show_leaderboard(self, ctx: Context, show_all=False):
        """Shows balance leaderboard."""
        query = '''SELECT * FROM currency'''
        records = await self.bot.pool.fetch(query)
        values = []
        for record in records:
            if m := ctx.guild.get_member(record['id']):
                values.append((m, float(record['money'])))
            elif show_all:
                async def get_or_fetch_user(user_id):
                    if user := self.bot.get_user(user_id):
                        return user
                    else:
                        try:
                            user = await self.bot.fetch_user(user_id)
                        except discord.HTTPException:
                            return
                        else:
                            return user
                values.append((await get_or_fetch_user(record['id']), float(record['money'])))
        _sorted = sorted(values, key=lambda v: v[1], reverse=True)
        table = tabulate(_sorted, headers=['user', 'money'], tablefmt='fancy_grid', floatfmt=',.2f', numalign='right')
        e = discord.Embed(title='Money Leaderboard',
                          description=f'```\n{table}\n```',
                          colour=bright_color(),
                          timestamp=datetime.datetime.utcnow())
        await ctx.send(embed=e)

    @_currency.command(name='get', aliases=['claim'])
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def claim_free_money(self, ctx: Context):
        balance = await get_balance(ctx, ctx.author)
        if balance <= 0:
            await ctx.reply('You do not have enough money to use this')
            self.claim_free_money.reset_cooldown(ctx)
            return
        bucket = self._claim_cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            decrease_amount = balance - (balance / 3)
            await set_balance(ctx, ctx.author, balance / 3)
            await ctx.tick(False)
            msg = f'You lost {decrease_amount:,.2f} (2/3 of your balance) due to anti-bot measures.'
            after = await get_balance(ctx, ctx.author)
        else:
            gain_amount = round(balance * 0.05, 2)
            await increase_balance(ctx, ctx.author, gain_amount)
            await ctx.tick()
            msg = f'You gained ${gain_amount:,.2f} (5% of your balance).'
            after = balance + gain_amount
        await ctx.reply(f'{msg} Balance: ${after:,.2f}')

    # @_currency.command(name='daily')
    # @commands.cooldown(1, 86400, commands.BucketType.user)
    # async def claim_daily_money(self, ctx):
    #     await increase_balance()


def setup(bot):
    bot.add_cog(Currency(bot))
