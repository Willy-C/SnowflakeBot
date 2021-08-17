import discord
import rapidfuzz
from discord.ext import commands
from utils.global_utils import copy_context


class Levenshtein(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_all_runnable_commands(self, ctx: commands.Context, include_aliases=False):
        all_command_names = []
        is_owner = await self.bot.is_owner(ctx.author)
        for command in self.bot.commands:
            command: commands.Command
            if await command.can_run(ctx):
                if not is_owner and command.hidden:
                    continue
                all_command_names.append(command.name)
                if include_aliases:
                    for alias in command.aliases:
                        all_command_names.append(alias)

        return all_command_names

    async def correct_command_name(self, ctx: commands.Context):
        runnable_commands = await self.get_all_runnable_commands(ctx, include_aliases=False)
        if not runnable_commands:
            return

        return rapidfuzz.process.extractOne(ctx.invoked_with,
                                            runnable_commands,
                                            scorer=rapidfuzz.string_metric.levenshtein,
                                            score_cutoff=1)

    async def confirm_correction(self, ctx: commands.Context, message: str):
        emojis = ['<:greenTick:602811779835494410>', '<:redTick:602811779474522113>']

        def confirm(r, u):
            return ctx.author.id == u.id and prompt == r.message and str(r.emoji) in emojis

        prompt = await ctx.reply(message)
        for e in emojis:
            await prompt.add_reaction(e)

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=confirm, timeout=60)
        except TimeoutError:
            return False
        else:
            return str(reaction.emoji) == '<:greenTick:602811779835494410>'
        finally:
            try:
                await prompt.delete()
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.CommandNotFound):
            correction = await self.correct_command_name(ctx)
            if not correction:
                return
            corrected_ctx = await copy_context(ctx,
                                               content=ctx.message.content.replace(ctx.invoked_with, correction[0], 1))

            do_correct = await self.confirm_correction(ctx, f'Did you mean `{correction[0]}` instead of `{ctx.invoked_with}`?')
            if not do_correct:
                return

            await self.bot.invoke(corrected_ctx)


def setup(bot):
    bot.add_cog(Levenshtein(bot))


