import discord
import pytz
from discord.ext import commands
from utils import errors


class CaseInsensitiveMember(commands.MemberConverter):
    async def convert(self, ctx, argument):
        try:
            member = await super().convert(ctx, argument)
        except commands.BadArgument:
            member = discord.utils.find(lambda m: m.name.lower() == argument.lower(), ctx.guild.members)
            if member is None:  # Nickname search
                member = discord.utils.find(lambda m: m.display_name.lower() == argument.lower(), ctx.guild.members)

        if member is None:
            raise errors.CaseInsensitiveMemberNotFound()
        return member


class Member(commands.MemberConverter):
    async def convert(self, ctx, argument):
        try:
            return await super().convert(ctx, argument)
        except commands.BadArgument:
            raise errors.MemberNotFound()


class CaseInsensitiveUser(commands.UserConverter):
    async def convert(self, ctx, argument):
        try:
            user = await super().convert(ctx, argument)
        except commands.BadArgument:
            user = discord.utils.find(lambda u: u.name.lower() == argument.lower(), ctx.bot.users)

        if user is None:
            raise errors.CaseInsensitiveUserNotFound()
        return user

# ID only
class CachedUserID(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            user = ctx.bot.get_user(int(argument))
        except ValueError:
            raise commands.BadArgument('That is not a valid ID')

        if user is None:
            raise commands.BadArgument(f'Unable to find User with ID {argument}')
        return user

# ID only
class CachedGuildID(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            guild = ctx.bot.get_guild(int(argument))
        except ValueError:
            raise commands.BadArgument('That is not a valid ID')

        if guild is None:
            raise commands.BadArgument(f'Unable to find Guild with ID {argument}')
        return guild


class Timezone(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.lower() in ('pst', 'pdt'):
            argument = 'US/Pacific'

        try:
            tz = pytz.timezone(argument)
        except pytz.UnknownTimeZoneError:
            raise errors.TimezoneNotFound()

        return tz


class CaseInsensitiveTextChannel(commands.TextChannelConverter):
    async def convert(self, ctx, argument):
        try:
            channel = await super().convert(ctx, argument)
        except commands.BadArgument:
            channel = discord.utils.find(lambda c: c.name.lower() == argument.lower(), ctx.guild.text_channels)

        if channel is None:
            raise errors.ChannelNotFound(f'Channel `{argument}` not found.')
        return channel


class CaseInsensitiveVoiceChannel(commands.VoiceChannelConverter):
    async def convert(self, ctx, argument):
        try:
            channel = await super().convert(ctx, argument)
        except commands.BadArgument:
            channel = discord.utils.find(lambda c: c.name.lower() == argument.lower(), ctx.guild.voice_channels)

        if channel is None:
            raise errors.ChannelNotFound(f'Channel `{argument}` not found.')
        return channel

