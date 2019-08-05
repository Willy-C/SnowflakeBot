import traceback
import sys
from discord.ext import commands
import discord

from .music import InvalidVoiceChannel, VoiceConnectionError


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
            return await ctx.send(f'{ctx.command} has been disabled. If you believe this is a mistake, please contact @Willy#7692')

        elif isinstance(error, commands.NoPrivateMessage):
            return await ctx.author.send(f'The command {ctx.prefix}{ctx.command} cannot be used in Private Messages.')

        elif isinstance(error, commands.CommandNotFound):
            return  # await ctx.send(f'The command `{ctx.invoked_with}` is not found.')

        elif isinstance(error, commands.BadArgument):
            return await ctx.send(f'One or more of arguments are incorrect. Please see {ctx.prefix}help for more info')

        elif isinstance(error, commands.NotOwner):
            return await ctx.send('Sorry, this command can only be used by my owner. If you believe this is a mistake, please contact @Willy#7692')

        elif isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send('Missing one or more required arguments.')

        elif isinstance(error, commands.MissingPermissions):
            return await ctx.send(f'Sorry, but you are missing the following permission{"" if len(error.missing_perms) == 1 else "s"}: {",".join(error.missing_perms)}')

        elif isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(f'Sorry, but I am missing the following permission{"" if len(error.missing_perms) == 1 else "s"}: {",".join(error.missing_perms)}')

        elif isinstance(error, InvalidVoiceChannel):
            return await ctx.send('No channel to join. Please either specify a valid channel or join one.')


        # print('Ignoring exception in command {}:'.format(ctx.command))
        # traceback.print_exception(type(error), error, error.__traceback__)
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
