import discord
from discord.ext import commands
from signal import SIGKILL
from config import SNEKBOX_URL
from utils.global_utils import cleanup_code, upload_hastebin


class EvalError(commands.CommandError):
    def __init__(self, status, message=None):
        self.status = status
        self.message = message or 'Something went wrong with this eval'


class Evaluation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['e'])
    @commands.max_concurrency(1, commands.BucketType.user)
    async def eval(self, ctx: commands.Context, *, code):
        """Evaluates your python code.
        Codeblocks are optional
        ```this is a codeblock``` """
        code = cleanup_code(code)
        async with ctx.typing():
            async with self.bot.session.post(f'{SNEKBOX_URL}/eval', json={'input': code}) as res:
                if res.status != 200:
                    raise EvalError(res.status, f'Something went wrong while sending your eval job.')
                data = await res.json()

            output = data['stdout'] or '<No output>'
            rcode = data['returncode']

            if rcode is None:
                raise EvalError(rcode, 'Your eval failed')
            elif rcode == 128 + SIGKILL:
                raise EvalError(rcode, 'Your eval timed out or ran out of memory')
            elif rcode == 255:
                raise EvalError(rcode, 'Something has gone horribly wrong')

            greentick = '<:greenTick:602811779835494410>'
            redtick = '<:redTick:602811779474522113>'
            emoji = greentick if rcode == 0 else redtick
            msg = f'{ctx.author.mention} {emoji} your eval completed with return code {rcode}'

            if len(output) >= 300:
                url = await upload_hastebin(ctx, output)
                await ctx.send(f'{msg}\nThe output is long so I uploaded it here: {url}')
            else:
                # don't want any codeblocks inside the output to break our output codeblock
                content = output.replace('```', "'''")
                await ctx.send(f'{msg}\n```py\n{content}\n```',
                               allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=[ctx.author]))

    @eval.error
    async def eval_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            ctx.local_handled = True
            if await self.bot.is_owner(ctx.author):  # Owner bypass
                return await ctx.reinvoke()
            return await ctx.send(f'{ctx.author.mention} Please wait until your previous eval job is finished before sending another')

        elif isinstance(error, EvalError):
            ctx.local_handled = True
            return await ctx.send(f'{ctx.author.mention} {error.message}\nStatus code: {error.status}')


def setup(bot):
    bot.add_cog(Evaluation(bot))
