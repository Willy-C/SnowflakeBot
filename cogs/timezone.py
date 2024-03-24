from __future__ import annotations

import asyncio
import datetime
import zoneinfo
from typing import TYPE_CHECKING, NamedTuple, Optional, Union, Annotated

import discord
from discord import app_commands
from discord.ext import commands
from lxml import etree

from utils.cache import cache
from utils.fuzzy import finder
from utils.time import UserFriendlyTime, FriendlyTimeResult, format_dt


if TYPE_CHECKING:
    from main import SnowflakeBot
    from utils.context import Context


class CLDRDataEntry(NamedTuple):
    description: str
    aliases: list[str]
    deprecated: bool
    preferred: Optional[str]


class TimeZone(NamedTuple):
    label: str
    key: str

    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> TimeZone:
        # assert isinstance(ctx.cog, Timezone)

        # Prioritise aliases because they handle short codes slightly better
        if argument in ctx.cog._timezone_aliases:
            return cls(key=argument, label=ctx.cog._timezone_aliases[argument])

        if argument in ctx.cog.valid_timezones:
            return cls(key=argument, label=argument)

        timezones = ctx.cog.find_timezones(argument)

        try:
            return await ctx.disambiguate(timezones, lambda t: t[0], ephemeral=True)
        except (ValueError, AttributeError):
            raise commands.BadArgument(f"Could not find timezone for {argument!r}")

    def to_choice(self) -> app_commands.Choice[str]:
        return app_commands.Choice(name=self.label, value=self.key)

    def to_zone(self) -> zoneinfo.ZoneInfo:
        return zoneinfo.ZoneInfo(self.key)


class Timezone(commands.Cog):

    DEFAULT_POPULAR_TIMEZONE_IDS = (
        # Canada
        "cator",  # America/Toronto
        "cavan",  # America/Vancouver
        "cawnp",  # America/Winnipeg

        # America
        "usnyc",  # America/New_York
        "uslax",  # America/Los_Angeles
        "uschi",  # America/Chicago
        "usden",  # America/Denver

        # Europe
        "trist",  # Europe/Istanbul
        "rumow",  # Europe/Moscow
        "gblon",  # Europe/London
        "frpar",  # Europe/Paris
        "esmad",  # Europe/Madrid
        "deber",  # Europe/Berlin
        "grath",  # Europe/Athens
        "uaiev",  # Europe/Kyev
        "itrom",  # Europe/Rome
        "nlams",  # Europe/Amsterdam
        "plwaw",  # Europe/Warsaw

        # Japan
        "jptyo",  # Asia/Tokyo
        # South Korea
        'krsel',  # Asia/Seoul
        # China
        "cnsha",  # Asia/Shanghai

        # Australia
        "aubne",  # Australia/Brisbane
        "ausyd",  # Australia/Sydney
        # India
        "inccu",  # Asia/Kolkata
        # Brazil
        "brsao",  # America/Sao_Paulo
    )

    def __init__(self, bot: SnowflakeBot):
        self.bot: SnowflakeBot = bot
        self.valid_timezones = zoneinfo.available_timezones()
        self._timezone_aliases: dict[str, str] = {
            'Eastern Time': 'America/New_York',
            'Central Time': 'America/Chicago',
            'Mountain Time': 'America/Denver',
            'Pacific Time': 'America/Los_Angeles',
            # (Unfortunately) special case American timezone abbreviations
            'EST': 'America/New_York',
            'CST': 'America/Chicago',
            'MST': 'America/Denver',
            'PST': 'America/Los_Angeles',
            'EDT': 'America/New_York',
            'CDT': 'America/Chicago',
            'MDT': 'America/Denver',
            'PDT': 'America/Los_Angeles',
        }
        self._default_timezones: list[app_commands.Choice[str]] = []

    async def cog_load(self) -> None:
        await self.parse_bcp47_timezones()

    async def parse_bcp47_timezones(self) -> None:
        async with self.bot.session.get(
            'https://raw.githubusercontent.com/unicode-org/cldr/main/common/bcp47/timezone.xml'
        ) as resp:
            if resp.status != 200:
                return

            parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
            tree = etree.fromstring(await resp.read(), parser=parser)

            # Build a temporary dictionary to resolve "preferred" mappings
            entries: dict[str, CLDRDataEntry] = {
                node.attrib['name']: CLDRDataEntry(
                    description=node.attrib['description'],
                    aliases=node.get('alias', 'Etc/Unknown').split(' '),
                    deprecated=node.get('deprecated', 'false') == 'true',
                    preferred=node.get('preferred'),
                )
                for node in tree.iter('type')
                # Filter the Etc/ entries (except UTC)
                if not node.attrib['name'].startswith(('utcw', 'utce', 'unk'))
                and not node.attrib['description'].startswith('POSIX')
            }

            for entry in entries.values():
                # These use the first entry in the alias list as the "canonical" name to use when mapping the
                # timezone to the IANA database.
                # The CLDR database is not particularly correct when it comes to these, but neither is the IANA database.
                # It turns out the notion of a "canonical" name is a bit of a mess. This works fine for users where
                # this is only used for display purposes, but it's not ideal.
                if entry.preferred is not None:
                    preferred = entries.get(entry.preferred)
                    if preferred is not None:
                        self._timezone_aliases[entry.description] = preferred.aliases[0]
                else:
                    self._timezone_aliases[entry.description] = entry.aliases[0]

            for key in self.DEFAULT_POPULAR_TIMEZONE_IDS:
                entry = entries.get(key)
                if entry is not None:
                    self._default_timezones.append(app_commands.Choice(name=entry.description, value=entry.aliases[0]))

    @cache(maxsize=10)
    async def get_timezone(self, user_id: int) -> Optional[str]:
        """Get the timezone for a user, if it exists."""
        query = '''SELECT tz FROM timezones WHERE id = $1;'''
        record = await self.bot.pool.fetchrow(query, user_id)
        return record['tz'] if record else None

    async def get_tzinfo(self, user_id: int) -> datetime.tzinfo:
        tz = await self.get_timezone(user_id)
        if tz is None:
            return datetime.UTC

        try:
            return zoneinfo.ZoneInfo(tz)
        except zoneinfo.ZoneInfoNotFoundError:
            return datetime.UTC

    def find_timezones(self, query: str) -> list[TimeZone]:
        # A bit hacky, but if '/' is in the query then it's looking for a raw identifier
        # otherwise it's looking for a CLDR alias
        if '/' in query:
            return [TimeZone(key=a, label=a) for a in finder(query, self.valid_timezones)]

        keys = finder(query, self._timezone_aliases.keys())
        return [TimeZone(label=k, key=self._timezone_aliases[k]) for k in keys]

    @commands.hybrid_group(case_insensitive=True, aliases=['tz', 'time'])
    async def timezone(self, ctx: Context):
        """Get or set your timezone"""
        await ctx.send_help(ctx.command)

    @timezone.command(name='get')
    @app_commands.describe(user='The user to get the timezone for. Defaults to yourself.')
    async def timezone_get(self, ctx: Context, *, user: discord.User = commands.Author):
        """Get a user's timezone."""
        tz = await self.get_timezone(user.id)
        if tz is None:
            await ctx.send(f'No timezone found for {user.mention}', allowed_mentions=discord.AllowedMentions.none())
            return

        time = discord.utils.utcnow().astimezone(zoneinfo.ZoneInfo(tz)).strftime('%Y-%m-%d %H:%M (%I:%M %p)')
        if user.id == ctx.author.id:
            msg = await ctx.send(f'Your timezone is set to: {tz}. Your current time is {time}')
            await asyncio.sleep(5)
            try:
                await msg.edit(content=f'Your current time is {time}')
            except discord.HTTPException:
                pass
        else:
            await ctx.send(f'The current time for {user.mention} is {time}',
                           allowed_mentions=discord.AllowedMentions.none())

    @timezone.command(name='set')
    @app_commands.describe(timezone='The timezone to set to.')
    async def timezone_set(self, ctx: Context, timezone: TimeZone):
        """Set your timezone.

        This is used to convert times to your local time when using other commands such as reminders.
        Use the slash command version of this command or [this website](https://zones.arilyn.cc/) to find your timezone.

        Note: Other users will be able to see your timezone
        """
        query = '''INSERT INTO timezones(id, tz)
                   VALUES($1, $2)
                   ON CONFLICT (id) DO UPDATE
                   SET tz=$2;'''
        await self.bot.pool.execute(query, ctx.author.id, timezone.key)

        self.get_timezone.invalidate(self, ctx.author.id)

        await ctx.send(f'Your timezone is now set to: {timezone.label} (IANA ID: {timezone.key})', ephemeral=True)

    @timezone.command('info')
    @app_commands.describe(timezone='The timezone to get info about.')
    async def timezone_info(self, ctx: Context, *, timezone: TimeZone):
        """Get info about a timezone"""
        embed = discord.Embed(title=timezone.key, colour=discord.Colour.blue())
        dt = discord.utils.utcnow().astimezone(zoneinfo.ZoneInfo(timezone.key))
        time = dt.strftime('%Y-%m-%d %H:%M (%I:%M %p)')
        embed.add_field(name='Current time', value=time)

        offset = dt.utcoffset()
        if offset is not None:
            minutes, _ = divmod(int(offset.total_seconds()), 60)
            hours, minutes = divmod(minutes, 60)
            embed.add_field(name='UTC Offset', value=f'{hours:+03d}:{minutes:02d}')

        await ctx.send(embed=embed)

    @timezone.command('remove')
    async def timezone_remove(self, ctx: Context):
        """Remove your timezone"""
        query = '''DELETE FROM timezones
                   WHERE id = $1;'''
        await self.bot.pool.execute(query, ctx.author.id)
        self.get_timezone.invalidate(self, ctx.author.id)
        await ctx.send('Your timezone has been removed', ephemeral=True)

    @timezone_set.autocomplete('timezone')
    @timezone_info.autocomplete('timezone')
    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if not current:
            return self._default_timezones
        matches = self.find_timezones(current)
        return [tz.to_choice() for tz in matches[:25]]

    @commands.command()
    async def timestamp(self, ctx: Context, *, time: Union[discord.User, discord.Message, discord.Object, Annotated[datetime.datetime, UserFriendlyTime(default='...')], str] = None):
        """Get the timestamp of a time or creation time of an object"""
        if isinstance(time, str):
            return await ctx.reply(f'Unable to parse time or object from `{time}`', mention_author=False)

        time = time or discord.utils.utcnow()
        if isinstance(time, FriendlyTimeResult):
            time = time.dt

        def build_timestamps(dt):
            styles = ['t', 'T', 'd', 'D', 'f', 'F', 'R']
            return [format_dt(dt, style) for style in styles]

        if isinstance(time, datetime.datetime):
            timestamps = build_timestamps(time)
            await ctx.reply('\n'.join(f'`{ts}` {ts}' for ts in timestamps), mention_author=False)
        else:
            title = f'Creation time for {getattr(time, "mention", time.id)}'
            timestamps = build_timestamps(discord.utils.snowflake_time(time.id))
            times = '\n'.join(f'`{ts}` {ts}' for ts in timestamps)
            await ctx.reply(f'{title}\n{times}',
                            allowed_mentions=discord.AllowedMentions.none(),
                            mention_author=False)


async def setup(bot: SnowflakeBot):
    await bot.add_cog(Timezone(bot))
