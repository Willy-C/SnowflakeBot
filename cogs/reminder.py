from __future__ import annotations

import asyncio
import textwrap
import datetime
import traceback
from typing import TYPE_CHECKING, Any, Optional, Self, Sequence, Annotated

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils import time

if TYPE_CHECKING:
    from main import SnowflakeBot
    from utils.context import Context
    from cogs.timezone import Timezone


class SnoozeModal(discord.ui.Modal, title='Snooze'):
    duration = discord.ui.TextInput(label='Duration', placeholder='10 minutes', default='10 minutes', min_length=2)

    def __init__(self, parent: ReminderView, reminder_cog: Reminders, timer: Timer) -> None:
        super().__init__()
        self.parent: ReminderView = parent
        self.timer: Timer = timer
        self.cog: Reminders = reminder_cog
        self.tzcog: Timezone = reminder_cog.bot.get_cog('Timezone')

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            when = time.FutureTime(str(self.duration)).dt
        except Exception:
            await interaction.response.send_message(
                'Duration could not be parsed, sorry. Try something like "5 minutes" or "1 hour"', ephemeral=True
            )
            return

        self.parent.snooze.disabled = True
        await interaction.response.edit_message(view=self.parent)

        zone = await self.tzcog.get_timezone(interaction.user.id)
        refreshed = await self.cog.create_timer(
            when,
            self.timer.event,
            *self.timer.args,
            **self.timer.kwargs,
            created=interaction.created_at,
            timezone=zone or 'UTC',
        )
        author_id, _, message = self.timer.args
        delta = time.human_timedelta(when, source=refreshed.created_at)
        await interaction.followup.send(
            f"Ok, I've snoozed your reminder for {delta}: {message}", ephemeral=True
        )


class SnoozeButton(discord.ui.Button['ReminderView']):
    def __init__(self, cog: Reminders, timer: Timer) -> None:
        super().__init__(label='Snooze', style=discord.ButtonStyle.blurple)
        self.timer: Timer = timer
        self.cog: Reminders = cog

    async def callback(self, interaction: discord.Interaction) -> Any:
        assert self.view is not None
        await interaction.response.send_modal(SnoozeModal(self.view, self.cog, self.timer))


class ReminderView(discord.ui.View):
    message: discord.Message

    def __init__(self, *, url: str, timer: Timer, cog: Reminders, author_id: int) -> None:
        super().__init__(timeout=300)
        self.author_id: int = author_id
        self.snooze = SnoozeButton(cog, timer)
        self.add_item(discord.ui.Button(url=url, label='Go to original message'))
        self.add_item(self.snooze)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message('This snooze button is not for you, sorry!', ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        self.snooze.disabled = True
        await self.message.edit(view=self)


class Timer:
    __slots__ = ('args', 'kwargs', 'event', 'id', 'created_at', 'expires', 'timezone')

    def __init__(self, *, record: asyncpg.Record):
        self.id: int = record['id']

        extra = record['extra']
        self.args: Sequence[Any] = extra.get('args', [])
        self.kwargs: dict[str, Any] = extra.get('kwargs', {})
        self.event: str = record['event']
        self.created_at: datetime.datetime = record['created']
        self.expires: datetime.datetime = record['expires']
        self.timezone: str = record['timezone']

    @classmethod
    def temporary(
        cls,
        *,
        expires: datetime.datetime,
        created: datetime.datetime,
        event: str,
        args: Sequence[Any],
        kwargs: dict[str, Any],
        timezone: str,
    ) -> Self:
        pseudo = {
            'id': None,
            'extra': {'args': args, 'kwargs': kwargs},
            'event': event,
            'created': created,
            'expires': expires,
            'timezone': timezone,
        }
        return cls(record=pseudo)

    def __eq__(self, other: object) -> bool:
        try:
            return self.id == other.id  # type: ignore
        except AttributeError:
            return False

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def human_delta(self) -> str:
        return time.format_relative(self.created_at)

    @property
    def author_id(self) -> Optional[int]:
        if self.args:
            return int(self.args[0])
        return None

    def __repr__(self) -> str:
        return f'<Timer created={self.created_at} expires={self.expires} event={self.event}>'


class Reminders(commands.Cog):
    def __init__(self, bot: SnowflakeBot):
        self.bot: SnowflakeBot = bot
        self._have_data: asyncio.Event = asyncio.Event()
        self._current_timer: Optional[Timer] = None
        self.weekly_check.start()
        self._task = bot.loop.create_task(self.dispatch_timers())

    async def cog_unload(self) -> None:
        self._task.cancel()
        self.weekly_check.cancel()

    async def get_active_timer(self, *, days: int) -> Optional[Timer]:
        query = '''SELECT * FROM timers WHERE expires < (now() + $1::interval) ORDER BY expires LIMIT 1'''
        record = await self.bot.pool.fetchrow(query, datetime.timedelta(days=days))
        if record:
            return Timer(record=record)

    async def call_timer(self, timer: Timer) -> None:
        """Delete the timer from the database and dispatch the event."""
        query = '''DELETE FROM timers WHERE id = $1'''
        await self.bot.pool.execute(query, timer.id)

        self.bot.dispatch(f'{timer.event}_timer_complete', timer)

    async def dispatch_timers(self) -> None:
        await self.bot.wait_until_ready()
        try:
            while not self.bot.is_closed():
                await self._have_data.wait()
                # can only asyncio.sleep for up to ~48 days reliably
                # so we're gonna cap it off at 40 days
                # see: http://bugs.python.org/issue20493

                # get the next active timer within 40 days
                # if there is no timer, we wait until we have data
                timer = self._current_timer = await self.get_active_timer(days=40)
                if timer is None:
                    self._have_data.clear()
                    continue

                now = discord.utils.utcnow()

                if timer.expires >= now:
                    to_sleep = (timer.expires - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(timer)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            # Just restart the task if we have a connection issue
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())
        except Exception as e:
            tb = traceback.format_exception(type(e), e, e.__traceback__)

            e = discord.Embed(title=f'A error occurred in the timer task',
                              color=discord.Color.red(),
                              timestamp=discord.utils.utcnow())

            await self.bot.owner.send(embed=e)
            await self.bot.owner.send(f'```py\n{"".join(tb)}```')
            raise

    async def short_timer(self, seconds: float, timer: Timer) -> None:
        await asyncio.sleep(seconds)
        self.bot.dispatch(f'{timer.event}_timer_complete', timer)

    async def create_timer(self, expires: datetime.datetime, event: str, *args: Any, **kwargs: Any) -> Timer:
        try:
            now = kwargs.pop('created')
        except KeyError:
            now = discord.utils.utcnow()

        tz_name = kwargs.pop('timezone', 'UTC')

        timer = Timer.temporary(event=event, args=args, kwargs=kwargs, expires=expires, created=now, timezone=tz_name)
        delta = (expires - now).total_seconds()
        if delta <= 60:
            self.bot.loop.create_task(self.short_timer(delta, timer))
            return timer

        query = '''INSERT INTO timers (event, created, expires, extra, timezone)
                   VALUES ($1, $2, $3, $4, $5) RETURNING id;'''

        row = await self.bot.pool.fetchrow(query, event, now, expires, {'args': args, 'kwargs': kwargs}, tz_name)
        timer.id = row['id']

        # only set if it is 40 days or less
        if delta <= (60 * 60 * 24 * 40):
            self._have_data.set()

        # check if new timer expires earlier than current one
        if self._current_timer and expires < self._current_timer.expires:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        return timer

    @commands.Cog.listener()
    async def on_reminder_timer_complete(self, timer: Timer) -> None:
        author_id, channel_id, message = timer.args
        dm_user = False
        try:
            channel = self.bot.get_channel(channel_id) or (await self.bot.fetch_channel(channel_id))
        except discord.HTTPException:
            # Channel not found or deleted, just DM the user
            dm_user = True
            guild_id = '@me'
            channel = None # silence the linter complaining about channel potentially not defined
        else:
            if channel.guild:
                guild_id = channel.guild.id
                guild = self.bot.get_guild(guild_id)

                if guild is None:
                    # We we left the guild, just DM the user
                    dm_user = True
                else:
                    member = guild.get_member(author_id)
                    member_perms = channel.permissions_for(member)
                    # If the member left the guild
                    # or they cannot read messages in the channel
                    # or we cannot send messages in the channel, then we DM them
                    if not member \
                            or not (member_perms.read_messages and member_perms.read_message_history) \
                            or not channel.permissions_for(guild.me).send_messages:
                        dm_user = True
            else:
                # Original channel was a DM
                dm_user = True
                guild_id = '@me'

        message_id = timer.kwargs.get('message_id')
        to_send = f'<@{author_id}> {timer.human_delta}: {message}'

        view = discord.utils.MISSING

        if message_id:
            url = f'https://discord.com/channels/{guild_id}/{channel_id}/{message_id}'
            view = ReminderView(url=url, timer=timer, cog=self, author_id=author_id)

        dest = self.bot.get_user(author_id) if dm_user else channel

        if not dest:
            return

        try:
            msg = await dest.send(to_send, view=view)
        except discord.HTTPException:
            pass
        else:
            if view is not discord.utils.MISSING:
                view.message = msg

    @commands.hybrid_group(aliases=['remind', 'timer'], usage='<time>')
    async def reminder(self, ctx: Context, *, when: Annotated[time.FriendlyTimeResult, time.UserFriendlyTime(commands.clean_content, default='…')]):
        """Set a reminder that sends a message after a certain amount of time.

        The input can be any direct date (e.g. YYYY-MM-DD) or a human
        readable offset. Examples:

        - 2d say happy birthday
        - next thursday buy milk
        - do the homework tomorrow
        - in 3 days study for exam
        """
        if len(when.arg) >= 1700:
            return await ctx.send('Reminder must be fewer than 1700 characters')

        tz_cog: Optional[Timezone] = self.bot.get_cog('Timezone')
        if not tz_cog:
            return await ctx.send('This command is not available at the moment, sorry')
        tz = await tz_cog.get_timezone(ctx.author.id)

        timer = await self.create_timer(
            when.dt,
            'reminder',
            ctx.author.id,
            ctx.channel.id,
            when.arg,
            created=ctx.message.created_at,
            message_id=ctx.message.id,
            timezone=tz or 'UTC'
        )

        msg = f'Ok, in {time.human_timedelta(when.dt, source=timer.created_at)}: {when.arg}'
        await ctx.send(msg)

    @reminder.app_command.command(name='set')
    @app_commands.describe(when='When to be reminded of something.', text='What to be reminded of')
    async def reminder_set(
        self,
        interaction: discord.Interaction,
        when: app_commands.Transform[datetime.datetime, time.TimeTransformer],
        text: app_commands.Range[str, 1, 1700] = '…',
    ):
        """Sets a reminder to remind you of something at a specific time."""
        await interaction.response.defer()
        message = await interaction.original_response()

        tz_cog: Optional[Timezone] = self.bot.get_cog('Timezone')
        if not tz_cog:
            return await interaction.followup.send('This command is not available at the moment, sorry')
        tz = await tz_cog.get_timezone(interaction.user.id)

        timer = await self.create_timer(
            when,
            'reminder',
            interaction.user.id,
            interaction.channel_id,
            text,
            created=interaction.created_at,
            message_id=message.id,
            timezone=tz or 'UTC',
        )
        delta = time.human_timedelta(when, source=timer.created_at)
        await interaction.followup.send(f"Ok, in {delta}: {text}")

    @reminder_set.error
    async def reminder_set_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, time.BadTimeTransform):
            await interaction.response.send_message(str(error), ephemeral=True)

    @reminder.command(name='list', ignore_extra=False)
    async def reminder_list(self, ctx: Context):
        """Lists your 10 upcoming reminders

        NOTE: This does not include reminders shorter than 1 minute total"""
        query = """SELECT id, expires, extra #>> '{args,2}'
                   FROM timers
                   WHERE event = 'reminder'
                   AND extra #>> '{args,0}' = $1
                   ORDER BY expires
                   LIMIT 10;
                """

        records = await self.bot.pool.fetch(query, str(ctx.author.id))

        if not records:
            return await ctx.send('You do not have any reminders set.')

        e = discord.Embed(colour=discord.Color.blue(), title='Reminders', timestamp=discord.utils.utcnow())

        if len(records) == 10:
            e.set_footer(text='Your upcoming 10 reminders')
        else:
            e.set_footer(text=f'{len(records)} reminder{"s" if len(records) > 1 else ""}')

        for _id, expires, message in records:
            shorten = textwrap.shorten(message, width=512, placeholder='...')
            e.add_field(name=f'{_id}: {time.format_relative(expires)}', value=shorten, inline=False)

        await ctx.send(embed=e)

    @reminder.command(name='cancel', aliases=['delete', 'remove'], ignore_extra=False)
    async def reminder_cancel(self, ctx: Context , *, id: int):
        """Cancels a reminder by ID
        See `%remind list` to get IDs"""
        query = """DELETE FROM timers
                   WHERE id=$1
                   AND event = 'reminder'
                   AND extra #>> '{args,0}' = $2;
                """

        result = await self.bot.pool.execute(query, id, str(ctx.author.id))

        if result == 'DELETE 0':
            return await ctx.send('Could not delete reminder with that ID. Are you sure you own that ID?\n'
                                  'You can see your reminders with `%remind list`')

        # if the current timer is being deleted, restart the task
        if self._current_timer and self._current_timer.id == id:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        await ctx.send(f'Deleted reminder {id}', ephemeral=True)

    # Force a data check once a week
    # Checks every 6day 23hr 45min
    # In case there is a timer coming up next week and no new timers triggered a check
    @tasks.loop(hours=167.75)
    async def weekly_check(self):
        self._have_data.set()

    @reminder_cancel.autocomplete('id')
    async def reminder_cancel_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        query = '''SELECT id, expires, extra #>> '{args,2}' 
                   FROM timers 
                   WHERE event = 'reminder' 
                   AND extra #>> '{args,0}' = $1 
                   ORDER BY expires 
                   LIMIT 25;'''
        reminders = await self.bot.pool.fetch(query, str(interaction.user.id))
        formatted = []
        for _id, expires, message in reminders:
            message = 'No message' if message == '…' else message
            formatted.append((_id, f' [ID: {_id}] {message} (in {time.human_timedelta(expires)})'))
        return [app_commands.Choice(name=str(message), value=str(_id)) for _id, message in formatted]


async def setup(bot: SnowflakeBot):
    await bot.add_cog(Reminders(bot))

