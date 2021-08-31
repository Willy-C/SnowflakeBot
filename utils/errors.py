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


class MessageNotFound(commands.BadArgument):
    def __init__(self, message=None):
        super().__init__(message or '```I am unable to find the specified message.\n'
                                    'I will search in the following order:\n\n'
                                    '1. By {channel ID}-{message ID}\n'
                                    'This can be retrieved by shift-clicking on “Copy ID”\n\n'
                                    '2. Lookup by message ID\n'
                                    'The message must be in the current channel\n\n'
                                    '3. Lookup by message URL\n\n'
                                    'Note: You need Developer Mode enabled to retrieve message IDs```')


class RoleNotFound(commands.BadArgument):
    def __init__(self, message=None):
        super().__init__(message or 'No role found with that name or ID')


class NoVoiceChannel(commands.CommandError):
    def __init__(self, message=None, *args) -> None:
        message = message or 'No voice channel to connect to. Please join one or use `%connect/join [channel]` first.'
        super().__init__(message, *args)
