import re
import traceback

import discord
from discord.ext import commands

from utils.context import Context
from utils.global_utils import upload_hastebin
from utils.errors import BlacklistedUser, TimezoneNotFound, NoVoiceChannel


class CommandErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.owner = None
        bot.on_error = self.on_error
        bot.loop.create_task(self.set_owner())

    async def set_owner(self):
        await self.bot.wait_until_ready()
        self.owner = (await self.bot.application_info()).owner

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error: commands.CommandError):
        """The event triggered when an error is raised while invoking a command.
        ctx   : Context
        error : Exception"""
        await self.bot.wait_until_ready()
        if getattr(ctx, 'local_handled', False):  # Check if handled by local error handlers
            return

        ignored = (commands.CommandNotFound, commands.CommandOnCooldown, BlacklistedUser, commands.NotOwner)  # Tuple of errors to ignore
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        elif isinstance(error, commands.DisabledCommand):
            return await ctx.send(f'Command `{ctx.command}` has been disabled.')

        elif isinstance(error, commands.NoPrivateMessage):
            return await ctx.author.send(f'The command `{ctx.command}` cannot be used in Private Messages.')

        elif isinstance(error, TimezoneNotFound):
            common = ['US/Eastern', 'US/Pacific', 'US/Central', 'US/Mountain']
            url = 'https://gist.githubusercontent.com/Willy-C/a511d95f1d28c1562332e487924f0d66/raw/5e6dfb0f1db4852eeaf1eb35ae4b1be92ca919e2/pytz_all_timezones.txt'
            e = discord.Embed(title='Timezones',
                              description=f'A full list of timezones can be found [here]({url})\n\n'
                                          f'Some common timezones include:\n '
                                          f'```{" | ".join(common)}```\n\n'
                                          f'Timezones are not case-sensitive',
                              colour=discord.Colour.blue())
            await ctx.send('Unable to find a timezone with that name', embed=e)
            return

        elif isinstance(error, NoVoiceChannel):
            await ctx.send(str(error))
            return

        elif isinstance(error, commands.BadArgument):
            return await ctx.send(f'Bad argument: {error}')

        elif isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f'Missing required argument: `{error.param.name}` See {ctx.prefix}help {ctx.command} for more info')

        elif isinstance(error, commands.MissingPermissions):
            return await ctx.send(f'I cannot complete this command, you are missing the following permission{"" if len(error.missing_permissions) == 1 else "s"}: {", ".join(error.missing_permissions)}')

        elif isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(f'I cannot complete this command, I am missing the following permission{"" if len(error.missing_permissions) == 1 else "s"}: {", ".join(error.missing_permissions)}')

        elif isinstance(error, commands.CheckFailure):
            return await ctx.send('Sorry, you cannot use this command')

        if self.owner is None:
            return

        # Unhandled error, so just return the traceback
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        await ctx.send(f'An unexpected error has occurred! My owner has been notified.\n'
                       f'If you really want to know what went wrong:\n'
                       f'||```py\n{tb[-1][:150]}```||')

        e = discord.Embed(title=f'An unhandled error occurred in {ctx.guild} | #{ctx.channel}',
                          description=f'Invocation message: {ctx.message.content}\n'
                                      f'[Jump to message]({ctx.message.jump_url})',
                          color=discord.Color.red())
        e.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)

        await self.owner.send(embed=e)
        fmt = "".join(tb)
        if len(fmt) >= 1980:
            url = await upload_hastebin(ctx, fmt)
            await self.owner.send(f'Traceback too long. {url}')
        else:
            await self.owner.send(f'```py\n{fmt}```')

    async def on_error(self, event, *args, **kwargs):
        await self.bot.wait_until_ready()
        await self.owner.send(f'An error occurred in event `{event}`')
        tb = "".join(traceback.format_exc())
        if len(tb) >= 1980:
            url = await upload_hastebin(self.bot, tb)
            await self.owner.send(f'Traceback too long. {url}')
        else:
            await self.owner.send(f'```py\n{tb}```')


def setup(bot):
    bot.add_cog(CommandErrorHandler(bot))


def teardown(bot):
    bot.on_error = commands.Bot.on_error
