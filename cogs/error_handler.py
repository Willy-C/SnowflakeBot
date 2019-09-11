import traceback
import sys
from discord.ext import commands
import discord

import re

from .music import InvalidVoiceChannel, VoiceConnectionError
from utils.errors import NoBlacklist
from .latex import TexRenderError


class CommandErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command.
        ctx   : Context
        error : Exception"""

        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (commands.CommandNotFound)  # Tuple of errors to ignore
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        elif isinstance(error, commands.DisabledCommand):
            return await ctx.send(f'`{ctx.command}` has been disabled. If you believe this is a mistake, please contact @Willy#7692')

        elif isinstance(error, commands.NoPrivateMessage):
            return await ctx.author.send(f'The command `{ctx.command}` cannot be used in Private Messages.')

        # elif isinstance(error, commands.CommandNotFound):
        #     return  # await ctx.send(f'The command `{ctx.invoked_with}` is not found.')

        elif isinstance(error, commands.BadArgument):
            return await ctx.send(f'One or more of arguments are incorrect. Please see {ctx.prefix}help for more info')

        elif isinstance(error, commands.NotOwner):
            return await ctx.send('Sorry, this command can only be used by my owner. If you believe this is a mistake, please contact @Willy#7692')

        elif isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send('Missing one or more required arguments.')

        elif isinstance(error, commands.MissingPermissions):
            return await ctx.send(f'I cannot complete this command, you are missing the following permission{"" if len(error.missing_perms) == 1 else "s"}: {", ".join(error.missing_perms)}')

        elif isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(f'I cannot complete this command, I am missing the following permission{"" if len(error.missing_perms) == 1 else "s"}: {", ".join(error.missing_perms)}')

        elif isinstance(error, InvalidVoiceChannel):
            return await ctx.send('No channel to join. Please either specify a valid channel or join one.')

        elif isinstance(error, NoBlacklist):
            return await ctx.send('You are blacklisted and cannot use this bot.')

        elif isinstance(error, TexRenderError):
            if error.logs is None :
                return await ctx.send('Rendering failed. Check your code.')

            err = re.search(r'^!.*?^!', error.logs + '\n!', re.MULTILINE + re.DOTALL)
            err_msg = err[0].strip("!\n")

            if len(err_msg) > 1000:
                return await ctx.send('Rendering failed. Please check your code.')
            return await ctx.send(f'Rendering failed.\n```{err_msg}```')

        # Unhandled error, so just return the traceback
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        await ctx.send(f'An unexpected error has occurred! My owner has been notified.\n'
                       f'If you really want to know what went wrong:\n'
                       f'||```py\n{tb[-1]}```||')

        me = self.bot.get_user(self.bot.owner_id)
        e = discord.Embed(title=f'An unhandled error occurred in {ctx.guild} | #{ctx.channel}',
                          description=f'Invocation message: {ctx.message.content}\n'
                                      f'[Jump to message]({ctx.message.jump_url})',
                          color=discord.Color.red())
        e.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

        await me.send(embed=e)
        await me.send(f'```py\n{"".join(tb)}```')


def setup(bot):
    bot.add_cog(CommandErrorHandler(bot))
