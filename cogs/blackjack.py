import data.blackjackgame as bj
from discord.ext import commands


class BlackJack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            ctx.local_handled = True
            await ctx.send('You already have an ongoing game!')

    @commands.max_concurrency(1, per=commands.BucketType.user)
    @commands.command(aliases=['bj'])
    async def blackjack(self, ctx, decks=4):
        """Play Blackjack in chat
        Can pass a number to specify the number of 52 card decks to shuffle together if you don't have an ongoing deck.
        (Defaults to 4 decks if not specified)
        You can use `%bjreset` to delete your deck and start over
        Note: Decks are per-user. Decks reset if number of cards remaining is less than 12
        """
        game = self.games.setdefault(ctx.author.id, bj.Game(ctx, decks=decks))
        await game.play_round(ctx)

    @commands.command(name='bjreset', hidden=True)
    async def reset_bj_deck(self, ctx):
        self.games.pop(ctx.author.id, None)
        await ctx.tick()


def setup(bot):
    bot.add_cog(BlackJack(bot))
