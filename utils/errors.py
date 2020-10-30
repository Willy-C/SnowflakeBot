import discord
from discord.ext import commands


class BlacklistedUser(commands.CheckFailure):
    def __init__(self, message=None):
        super().__init__(message or 'You are blacklisted and cannot use this bot.')


class CaseInsensitiveMemberNotFound(commands.BadArgument):
    def __init__(self, message=None):
        super().__init__(message or '```No user found on this server matching that name.\n'
                                    'I will search in this order: \n'
                                    '1. By ID                     (ex. 54295190266996)\n'
                                    '2. By Mention                (ex. @Snowflake)\n'
                                    '3. By Name#Discrim           (ex. Snowflake#7321)\n'
                                    '4. By Name                   (ex. Snowflake)\n'
                                    '5. By Nickname               (ex. BeepBoop)\n'
                                    '6. By Name*                  (ex. SNOWFLAKE)\n'
                                    '7. By Nickname*              (ex. BEEPBOOP)\n'
                                    '* = case-insensitive search```')


class MemberNotFound(commands.BadArgument):
    def __init__(self, message=None):
        super().__init__(message or '```No user found on this server matching that name.\n'
                                    'I will search in this order: \n'
                                    '1. By ID                     (ex. 54295190266996)\n'
                                    '2. By Mention                (ex. @Snowflake)\n'
                                    '3. By Name#Discrim           (ex. Snowflake#7321)\n'
                                    '4. By Name                   (ex. Snowflake)\n'
                                    '5. By Nickname               (ex. BeepBoop)\n'
                                    'Note: Names are Case-sensitive!```')


class CaseInsensitiveUserNotFound(commands.BadArgument):
    def __init__(self, message=None):
        super().__init__(message or '```No user found matching that name.\n'
                                    'I will search in this order: \n'
                                    '1. By ID                     (ex. 54295190266996)\n'
                                    '2. By Mention                (ex. @Snowflake)\n'
                                    '3. By Name#Discrim           (ex. Snowflake#7321)\n'
                                    '4. By Name                   (ex. Snowflake)\n'
                                    '5. By Name*                  (ex. SNOWFLAKE)\n'
                                    '* = case-insensitive search```')


class UserNotFound(commands.BadArgument):
    def __init__(self, message=None):
        super().__init__(message or '```No user found matching that name.\n'
                                    'I will search in this order: \n'
                                    '1. By ID                     (ex. 54295190266996)\n'
                                    '2. By Mention                (ex. @Snowflake)\n'
                                    '3. By Name#Discrim           (ex. Snowflake#7321)\n'
                                    '4. By Name                   (ex. Snowflake)\n'
                                    'Note: Names are Case-sensitive!```')


class TimezoneNotFound(commands.CommandError):
    pass


class ChannelNotFound(commands.BadArgument):
    def __init__(self, message=None):
        super().__init__(message or 'No channel found with that name or ID')


class NoGuildEmojis(commands.CommandError):
    def __init__(self, message=None):
        self.message = message or 'This server does not have any emojis. <:k3llySad:771583555193143326>'
