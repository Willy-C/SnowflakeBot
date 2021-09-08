import data.blackjackgame as bj
from discord.ext import commands
from utils.converters import CurrencyConverter


class DecksFlag(commands.FlagConverter):
    decks: int = 4


class Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            ctx.local_handled = True
            await ctx.send('You already have an ongoing game!')

    @commands.max_concurrency(1, per=commands.BucketType.user)
    @commands.command(aliases=['bj'], usage='<bet> [decks:4]')
    async def blackjack(self, ctx, bet: CurrencyConverter = 0, *, flags: DecksFlag):
        """Play Blackjack in chat
        You can pass a number to specify your bet

        You can also specify the number of decks to use
        (Defaults to 4 decks if not specified)
        You can use `%bjreset` to delete your deck and start over
        Note: Decks are per-user. Decks reset if number of cards remaining is less than 12

        Example:
            `%bj` Play a game with no bet
            `%bj 100` Play a game with a $100 bet
            `%bj 100 decks:6` Start a game with a $100 bet and 6 decks (only works if you don't have a game already. You will have to use `%bjreset` first if you have an existing deck)
        """

        cog = self.bot.get_cog('Currency')
        if not cog:
            return await ctx.send('Sorry, this command is unavailable at the moment')
        balance = await cog.get_balance(ctx.author)
        if bet > balance:
            return await ctx.reply(f'You do not have enough money to bet ${bet}. (Balance: ${balance})')
        game = self.games.setdefault(ctx.author.id, bj.Game(ctx, decks=flags.decks))
        await game.play_round(ctx, bet)

    @commands.command(name='bjreset', aliases=['resetbj', 'blackjackreset'], hidden=True)
    async def reset_bj_deck(self, ctx):
        self.games.pop(ctx.author.id, None)
        await ctx.tick()


def setup(bot):
    bot.add_cog(Game(bot))
