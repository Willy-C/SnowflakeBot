import discord
from discord.ext import commands

import datetime
import unicodedata

class GeneralCog(commands.Cog, name='General'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def quote(self, ctx, user: discord.Member, *, message: commands.clean_content()):
        """Send a message as someone else"""
        webhook = await ctx.channel.create_webhook(name=user.display_name)
        await webhook.send(message, avatar_url=user.avatar_url_as(format='png'))
        await webhook.delete()
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name='poll')
    async def create_poll(self, ctx, *questions_and_choices: str):
        """Makes a poll.
        Ex. %poll "question here" "answer 1" answer2 "answer 3"...
        " " Quotations only necessary if there are spaces.
        """
        if len(questions_and_choices) < 3:
            await ctx.send('Need at least 1 question with 2 choices.')
            return await ctx.send(f'Ex. {ctx.prefix}poll "Is this bot good?" Yes No "Answer with spaces must be quoted" Maybe')
        elif len(questions_and_choices) > 21:
            return await ctx.send('You can only have up to 20 choices.')

        perms = ctx.channel.permissions_for(ctx.me)
        if not (perms.read_message_history or perms.add_reactions):
            return await ctx.send('Need Read Message History and Add Reactions permissions.')

        question = questions_and_choices[0]
        choices = [(to_emoji(e), v) for e, v in enumerate(questions_and_choices[1:])]

        try:
            await ctx.message.delete()
        except:
            pass

        body = "\n".join(f"{key}: {c}" for key, c in choices)
        e = discord.Embed(color=0xFFFF00, timestamp=datetime.datetime.utcnow())
        e.set_footer(text=ctx.author)
        e.add_field(name=f'{question}', value=body)
        poll = await ctx.send(embed=e)

        for emoji, _ in choices:
            await poll.add_reaction(emoji)

    @commands.command()
    async def charinfo(self, ctx, *, characters: str):
        """Gives you information about character(s).
        Only up to 25 characters at a time.
        """

        def to_string(c):
            digit = f'{ord(c):x}'
            name = unicodedata.name(c, 'Name not found.')
            return f'`\\U{digit:>08}`: {name} \U00002014 {c} \U00002014 <http://www.fileformat.info/info/unicode/char/{digit}>'

        msg = '\n'.join(map(to_string, characters))
        if len(msg) > 2000:
            await ctx.send('Up to 25 characters at a time and no custom emojis!', delete_after=5)
            return await ctx.send('Output too long to display.')
        await ctx.send(msg)


def to_emoji(c):
    base = 0x1f1e6
    return chr(base + c)


def setup(bot):
    bot.add_cog(GeneralCog(bot))
