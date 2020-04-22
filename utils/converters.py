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


class CaseInsensitiveUser(commands.UserConverter):
    async def convert(self, ctx, argument):
        try:
            user = await super().convert(ctx, argument)
        except commands.BadArgument:
            user = discord.utils.find(lambda u: u.name.lower() == argument.lower(), ctx.bot.users)

        if user is None:
            raise errors.CaseInsensitiveUserNotFound()
        return user


class Timezone(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.lower() in ('pst', 'pdt'):
            argument = 'US/Pacific'

        try:
            tz = pytz.timezone(argument)
        except pytz.UnknownTimeZoneError:
            raise errors.TimezoneNotFound()

        return tz
