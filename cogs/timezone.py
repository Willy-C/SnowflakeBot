import discord
from discord.ext import commands

import datetime
from pytz import utc
from typing import Union
from utils.global_utils import get_user_timezone
from utils.converters import CaseInsensitiveMember, Timezone


class TimezoneCog(commands.Cog, name='Timezones'):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='timezone', aliases=['tz'], invoke_without_command=True, case_insensitive=True)
    async def tz_group(self, ctx, *, arg: Union[CaseInsensitiveMember, Timezone] = 0):
        """Timezone settings
        Setting your timezone allows for reminders to use your timezone

        Ex: `%remind local do homework at 4pm tomorrow`
        Will trigger at 4pm in your timezone if set, otherwise it will trigger at 4pm UTC
        """
        # Should never be able to input 0, using 0 here instead of None because Timezone can return None
        if isinstance(arg, discord.Member) or arg == 0:
            await ctx.invoke(self.get_timezone, user=(arg or ctx.author))
        elif arg is None:
            await ctx.invoke(self.list_timezones)
        else:
            await ctx.invoke(self.set_timezone, arg)

    @tz_group.command(name='get')
    async def get_timezone(self, ctx, *, user: CaseInsensitiveMember = None):
        """Retrieve your timezone setting
        Pass in a user to retrieve someone else's timezone"""
        user = user or ctx.author
        timezone = await get_user_timezone(ctx, user)
        if timezone is not None:
            now = utc.localize(datetime.datetime.utcnow())
            who = "Your" if user == ctx.author else f"{user}'s"
            await ctx.send(f'{who} timezone is set to: {timezone.zone} - Current time: {now.astimezone(timezone).strftime("%Y-%m-%d %H:%M")}  ')
        else:
            if user == ctx.author:
                await ctx.send('Unable to find your timezone. Are you sure you set one? See `%help timezone`')
            else:
                await ctx.send('Unable to find timezone for this user.')

    @tz_group.command(name='set')
    async def set_timezone(self, ctx, timezone: Timezone):
        """Set your timezone
        See `%timezone list` for all valid timezone names"""
        query = '''INSERT INTO timezones("user", tz)
                   VALUES($1, $2)
                   ON CONFLICT ("user") DO UPDATE
                   SET tz=$2;'''
        await self.bot.pool.execute(query, ctx.author.id, timezone.zone)
        now = utc.localize(datetime.datetime.utcnow())
        await ctx.send(f'Your timezone is now set to: {timezone.zone} - Current time: {now.astimezone(timezone).strftime("%Y-%m-%d %H:%M")}')

    @tz_group.command(name='list')
    async def list_timezones(self, ctx):
        """View all available timezones to choose from"""
        common = ['US/Eastern', 'US/Pacific', 'US/Central', 'US/Mountain']
        url = 'https://gist.githubusercontent.com/Willy-C/a511d95f1d28c1562332e487924f0d66/raw/5e6dfb0f1db4852eeaf1eb35ae4b1be92ca919e2/pytz_all_timezones.txt'
        e = discord.Embed(title='Timezones',
                          description=f'A full list of timezones can be found [here]({url})\n\n'
                                      f'Some common timezones include:\n '
                                      f'```{" | ".join(common)}```\n\n'
                                      f'Timezones are not case-sensitive',
                          colour=discord.Colour.blue())
        await ctx.send(embed=e)

    @tz_group.command(name='delete', aliases=['remove'])
    async def delete_timezone(self, ctx):
        """Delete your stored timezone information"""
        query = '''DELETE FROM timezones
                   WHERE "user" = $1'''
        result = await self.bot.pool.execute(query, ctx.author.id)

        if result == 'DELETE 0':
            return await ctx.send('Unable to delete your timezone info. Are you sure you set one?')
        else:
            await ctx.send('Successfully deleted your timezone info.')

    @tz_group.command(name='info')
    async def timezone_info(self, ctx, timezone: Timezone):
        """Get the current time of a timezone"""
        now = utc.localize(datetime.datetime.utcnow())
        await ctx.send(f'Current time in {timezone.zone}: {now.astimezone(timezone).strftime("%Y-%m-%d %H:%M")}')

    @tz_group.error
    async def set_tz_error(self, ctx, error):
        if isinstance(error, (commands.BadUnionArgument, commands.BadArgument)):
            ctx.local_handled = True
            await ctx.send('Unable to find that person/timezone')

    @commands.command(name='time')
    async def get_user_time(self, ctx, user: CaseInsensitiveMember = None):
        await ctx.invoke(self.get_timezone, (user or ctx.author))


def setup(bot):
    bot.add_cog(TimezoneCog(bot))
