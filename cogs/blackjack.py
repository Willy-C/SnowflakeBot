from discord.ext import commands
from data.blackjackgame import Game


class BlackJack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    @commands.command(aliases=['bj'])
    async def blackjack(self, ctx, decks=4):
        game = self.games.setdefault(ctx.author.id, Game(ctx, decks=decks))
        await game.play_round(ctx)
        if len(game.deck) < 10:
            del self.games[ctx.author.id]


def setup(bot):
    bot.add_cog(BlackJack(bot))
