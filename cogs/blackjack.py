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
        game = self.games.setdefault(ctx.author.id, bj.Game(ctx, decks=decks))
        await game.play_round(ctx)
        await game.calculate_outcome()
        if len(game.deck) < 10:
            del self.games[ctx.author.id]


def setup(bot):
    bot.add_cog(BlackJack(bot))
