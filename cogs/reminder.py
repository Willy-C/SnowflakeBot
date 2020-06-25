import discord
from discord.ext import commands, tasks

import asyncio
import traceback
import datetime
from textwrap import shorten

from utils.time import UserFriendlyTime, human_timedelta
from utils.global_utils import get_user_timezone


class ReminderCog(commands.Cog, name='Reminders'):

    def __init__(self, bot):
        self.bot = bot
        self.have_timer = asyncio.Event()
        self.current_timer = None
        self.weekly_check.start()
        self.task = bot.loop.create_task(self.timer_task())

    def cog_unload(self):
        self.task.cancel()
        self.weekly_check.cancel()

    async def get_timer(self):
        query = 'SELECT * FROM reminders WHERE "end" <  (CURRENT_DATE + $1::interval) ORDER BY "end" LIMIT 1;'
        return await self.bot.pool.fetchrow(query, datetime.timedelta(days=7))

    async def run_timer(self, timer):
        query = 'DELETE FROM reminders WHERE id=$1;'
        await self.bot.pool.execute(query, timer['id'])

        self.bot.dispatch(f'{timer["event"]}_complete', timer)

    async def timer_task(self):
        await self.bot.wait_until_ready()
        try:
            while not self.bot.is_closed():
                await self.have_timer.wait()
                upcoming = self.current_timer = await self.get_timer()
                if upcoming is None:
                    self.have_timer.clear()
                    continue
                now = datetime.datetime.utcnow()
                if upcoming['end'] >= now:
                    sleep_time = (upcoming['end'] - now).total_seconds()
                    await asyncio.sleep(sleep_time)
                await self.run_timer(upcoming)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            owner = (await self.bot.application_info()).owner
            tb = traceback.format_exception(type(e), e, e.__traceback__)

            e = discord.Embed(title=f'A error occurred in the timer task',
                              color=discord.Color.red(),
                              timestamp=datetime.datetime.utcnow())

            await owner.send(embed=e)
            await owner.send(f'```py\n{"".join(tb)}```')

    async def short_timer(self, seconds, user=None, channel=None, message=None, content=None, event='reminder'):
        start = datetime.datetime.utcnow()
        await asyncio.sleep(seconds)
        mock = {
            'user': user,
            'channel': channel,
            'message': message,
            'content': content,
            'start': start
        }
        self.bot.dispatch(f'{event}_complete', mock)

    async def create_timer(self, end, user, channel, message, content=None, event='reminder', start=None):
        now = start or datetime.datetime.utcnow()
        channel_id = channel if isinstance(channel, int) else getattr(channel, 'id', None)
        message_id = message if isinstance(message, int) else getattr(message, 'id', None)
        delta = (end - now).total_seconds()
        if delta <= 60:
            self.bot.loop.create_task(self.short_timer(delta, user.id, channel_id, message_id, content, event))
            return
        query = """INSERT INTO reminders (start, "end", "user", channel, message, content, event)
                   VALUES ($1, $2, $3, $4, $5, $6, $7);"""
        await self.bot.pool.execute(query, now, end, user.id, channel_id, message_id, content, event)
        if delta <= (86400 * 40):  # 40 days
            self.have_timer.set()

        if self.current_timer and end < self.current_timer['end']:
            self.task.cancel()
            self.task = self.bot.loop.create_task(self.timer_task())

    @commands.Cog.listener()
    async def on_reminder_complete(self, timer):
        user = self.bot.get_user(timer.get('user'))
        if user is None:
            # rip
            return

        cid = timer.get('channel')
        message_id = timer.get('message')
        message = timer.get('content')
        channel = self.bot.get_channel(cid)

        if cid is not None:
            if channel is not None:
                guild_id = channel.guild.id
                channel_id = channel.id

                member = channel.guild.get_member(user.id)
                if not member or not channel.permissions_for(member).read_messages:
                    channel = user
                    message_id = None  # No jump url if user can't access channel
                elif member and not channel.permissions_for(channel.guild.me).send_messages:
                    channel = user
            else:
                channel = user
                message_id = None

        else:
            channel = user
            guild_id = '@me'
            channel_id = (await user.create_dm()).id

        delta = human_timedelta(timer.get("start"))
        if message_id:
            url = f'<https://discordapp.com/channels/{guild_id}/{channel_id}/{message_id}>'
            msg = f'{user.mention} {delta}: {message}\n\n{url}'
        else:
            msg = f'{user.mention} {delta}: {message}'

        try:
            await channel.send(msg)
        except discord.HTTPException:
            pass

    @commands.group(name='remind', aliases=['reminder', 'timer'], invoke_without_command=True, case_insensitive=True)
    async def reminder(self, ctx, *, time: UserFriendlyTime(commands.clean_content, default='\u2026')):
        """Set a reminder that sends a message after a certain amount of time.

        The input can be any direct date (e.g. YYYY-MM-DD) or a human
        readable offset. Examples:

        - 2d say happy birthday
        - next thursday buy milk
        - do the homework tomorrow
        - in 3 days study for exam

        NOTE: Times are in UTC.
        For absolute times (ex. 4pm), it is recommended to use the `local` version, see `%help remind local`
        """
        now = datetime.datetime.utcnow()
        await self.create_timer(time.dt, ctx.author, ctx.channel, ctx.message, time.arg, 'reminder', start=now)
        await ctx.send(f'Ok, in {human_timedelta(time.dt, source=now)}: {time.arg}')

    @reminder.command(name='local', aliases=['l'])
    async def local_reminder(self, ctx, *, time: UserFriendlyTime(commands.clean_content)):
        """Similar to the normal `remind` command but tries to convert the end time to your local timezone

        Ex: `%remind local do homework at 4pm tomorrow`
        Will trigger at 4pm in your timezone if set, otherwise it will trigger at 4pm UTC
        See `%help timezone` on how to set your timezone

        NOTE: It is not recommended to use a __relative time__ with this command, for that, use the regular `%remind ...`

        Example of __relative time__: `%remind me in 5 seconds...` this will NOT trigger in 5 seconds if your timezone is not set to UTC"""
        tz = await get_user_timezone(ctx, ctx.author)
        if tz is None:
            return await ctx.send('No timezone found. See `%help tz set` on how to set a timezone')
        await ctx.invoke(self.reminder, time=time)

    @reminder.command(name='list')
    async def list_reminders(self, ctx):
        """Lists your 10 upcoming reminders
        NOTE: This does not include reminders shorter than 1 minute total"""
        query = '''SELECT id, "end", content
                   FROM reminders
                   WHERE event = 'reminder'
                   AND "user" = $1
                   ORDER BY "end" ASC
                   LIMIT 10;'''

        reminders = await self.bot.pool.fetch(query, ctx.author.id)
        if not reminders:
            return await ctx.send('You do not have any reminders set')

        e = discord.Embed(title='Reminders',
                          color=discord.Color.blue(),
                          timestamp=datetime.datetime.utcnow())
        if len(reminders) == 10:
            e.set_footer(text='Your upcoming 10 reminders')
        else:
            e.set_footer(text=f'{len(reminders)} reminder{"s" if len(reminders)>1 else ""}')

        for _id, end, content in reminders:
            fmt = shorten(content, width=512, placeholder='...')
            e.add_field(name=f'{_id}: In {human_timedelta(end)}', value=fmt, inline=False)

        await ctx.send(embed=e)

    @reminder.command(name='cancel', aliases=['delete', 'remove'])
    async def cancel_reminder(self, ctx, id: int):
        """Cancels a reminder by ID
        See `%remind list` to get IDs"""
        query = '''DELETE FROM reminders
                   WHERE id = $1
                   AND "user" = $2 
                   AND event = 'reminder';'''
        result = await self.bot.pool.execute(query, id, ctx.author.id)

        if result == 'DELETE 0':
            return await ctx.send('Could not delete reminder with that ID. Are you sure you own that ID?\n'
                                  'You can see your reminders with `%remind list`')

        if self.current_timer and self.current_timer['id'] == id:
            self.task.cancel()
            self.task = self.bot.loop.create_task(self.timer_task())

        await ctx.send(f'Deleted reminder {id}')

    # Force a data check once a week
    # Checks every 6day 23hr 45min
    # In case there is a timer coming up next week and no new timers triggered a check
    @tasks.loop(hours=167.75)
    async def weekly_check(self):
        self.have_timer.set()


def setup(bot):
    bot.add_cog(ReminderCog(bot))
