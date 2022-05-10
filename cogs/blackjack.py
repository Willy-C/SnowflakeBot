import random

from discord.ext import commands

import data.blackjackgame as bj
from utils.context import Context
from utils.converters import MoneyConverter
from utils.views import TWOMView
from utils.currency import get_balance, increase_balance, decrease_balance


class DecksFlag(commands.FlagConverter):
    decks: int = 6


class Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            ctx.local_handled = True
            await ctx.send('You already have an ongoing game!')

        elif isinstance(error, commands.BadUnionArgument):
            await ctx.send('That is not a valid number')
            ctx.local_handled = True

    @commands.max_concurrency(1, per=commands.BucketType.user)
    @commands.command(aliases=['bj'], usage='<bet> [decks:6]')
    async def blackjack(self, ctx: Context, bet: MoneyConverter = 0, *, flag: DecksFlag):
        """Play Blackjack in chat
        You can pass a number to specify your bet

        You can also specify the number of decks to use
        (Defaults to 6 decks if not specified, max 8)
        You can use `%bjreset` to delete your deck and start over
        Note: Decks are per-user. Decks reset if number of cards remaining is less than 12

        Example:
            `%bj` Play a game with no bet
            `%bj 100` Play a game with a $100 bet
            `%bj 100 decks:6` Start a game with a $100 bet and 6 decks (only works if you don't have a game already. You will have to use `%bjreset` first if you have an existing deck)
        """
        balance = await get_balance(ctx, ctx.author)
        if not isinstance(bet, float):
            if bet == 'all':
                bet = balance
            elif bet == 'half':
                bet = balance / 2
        if bet > balance:
            return await ctx.reply(f'You do not have enough money to bet ${bet:,.2f}. (Balance: ${balance:,.2f})')
        decks = max(1, min(flag.decks, 8))
        game = self.games.setdefault(ctx.author.id, bj.Game(ctx, decks=decks))
        await game.play_round(ctx, bet)

    @commands.command(name='bjreset', aliases=['resetbj', 'blackjackreset'], hidden=True)
    async def reset_bj_deck(self, ctx):
        self.games.pop(ctx.author.id, None)
        await ctx.tick()

    @commands.command(name='twom')
    async def twom_guessing_game(self, ctx: Context, bet: MoneyConverter=0):
        """Emulate an old number guess game in TWOM (The World of Magic)
        Objective of the game is to guess if a randomly generated number is even or odd.
        However, multiples of 5s is an automatic loss even with a correct guess.
        """
        if bet != 0:

            balance = await get_balance(ctx, ctx.author)
            if not isinstance(bet, float):
                if bet == 'all':
                    bet = balance
                elif bet == 'half':
                    bet = balance / 2
            if bet > balance:
                return await ctx.reply(f'You do not have enough money to bet ${bet:,.2f}. (Balance: ${balance:,.2f})')
            await decrease_balance(ctx, ctx.author, bet)

        view = TWOMView(player=ctx.author)
        view.message = await ctx.reply('Guess if the number is even or odd.', view=view)
        answer = random.randint(1, 100)
        await view.wait()
        is_even = view.even

        if answer % 5 == 0:
            won = False
            await ctx.reply(f'The number was {answer}, it is a multiple of 5. You lose.')
        elif (answer % 2 == 0 and is_even) or (answer % 2 != 0 and not is_even):
            won = True
            await ctx.reply(f'The number was {answer}. You win!')
        else:
            won = False
            await ctx.reply(f'The number was {answer}. You lose!')

        if bet != 0:
            if won:
                amount = bet*2
                await increase_balance(ctx, ctx.author, amount)


def setup(bot):
    bot.add_cog(Game(bot))
