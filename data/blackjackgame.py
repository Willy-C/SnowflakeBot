import random
from textwrap import dedent
import discord
from discord.ext import commands
from aenum import Enum, IntEnum, NoAlias
from utils.currency import increase_balance, decrease_balance, get_balance


class CardValue(IntEnum, settings=NoAlias):
    Ace   = 1
    Two   = 2
    Three = 3
    Four  = 4
    Five  = 5
    Six   = 6
    Seven = 7
    Eight = 8
    Nine  = 9
    Ten   = 10
    Jack  = 10
    Queen = 10
    King  = 10


class CardSuit(Enum):
    Diamonds = 1
    Clubs    = 2
    Hearts   = 3
    Spades   = 4


class HandState(Enum):
    PLAYING   = 1
    BLACKJACK = 2
    BUST      = 3
    HIDDEN    = 4


class GamePhase(Enum):
    IDLE    = 1
    PLAYER  = 2
    DEALER  = 3
    END     = 4
    NATURAL = 5
    DEALER_NATURAL = 6


class GameResult(Enum):
    WIN  = 1
    LOSS = 2
    TIE  = 3
    NATURAL = 4


class PlayerChoice(Enum):
    HIT = 1
    STAND = 2
    DOUBLE = 3
    SURRENDER = 4

display_cards = {
    'Ace':   'A',
    'Two':   '2',
    'Three': '3',
    'Four':  '4',
    'Five':  '5',
    'Six':   '6',
    'Seven': '7',
    'Eight': '8',
    'Nine':  '9',
    'Ten':   '10',
    'Jack':  'J',
    'Queen': 'Q',
    'King':  'K'
}

display_suits = {
    'Diamonds': '♦',
    'Clubs'   : '♣',
    'Hearts'  : '❤',
    'Spades'  : '♠'
}


class BlackJackView(discord.ui.View):
    def __init__(self, game=None):
        super().__init__(timeout=3600)
        self.choice = None
        self.message = None
        self.game: Game = game
        self.player = game.ctx.author

    async def disable(self):
        for c in self.children:
            c.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None:
            return False
        if interaction.user == self.player:
            return True
        else:
            await interaction.response.send_message('This game is not yours', ephemeral=True)
            return False

    @discord.ui.button(label='Hit', style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.double.disabled = True
        self.surrender.disabled = True
        self.choice = PlayerChoice.HIT
        self.game.save_choice(self.choice)
        self.game.player.add_card(self.game.deck.draw_card())
        if self.game.player.state is HandState.BUST:
            self.game.phase = GamePhase.END
        if self.game.player.state is HandState.BLACKJACK:
            self.game.phase = GamePhase.DEALER
        await interaction.response.edit_message(embed=self.game.build_game_embed(), view=self)
        if self.game.phase is not GamePhase.PLAYER:
            self.stop()

    @discord.ui.button(label='Stand', style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.choice = PlayerChoice.STAND
        self.game.save_choice(self.choice)
        self.game.phase = GamePhase.DEALER
        self.stop()

    @discord.ui.button(label='Double', style=discord.ButtonStyle.blurple)
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.game.is_betting:
            await interaction.response.send_message(f'You are not betting!',
                                                    ephemeral=True)
            return
        balance = await get_balance(self.game.ctx, self.game.ctx.author)
        if balance < self.game.bet:
            await interaction.response.send_message(f'You do not have enough money to double to ${self.game.bet * 2}. (Balance: ${balance:,.2f}, need ${self.game.bet})',
                                                    ephemeral=True)
            return
        await decrease_balance(self.game.ctx, self.game.ctx.author, self.game.bet)
        self.game.bet *= 2
        self.choice = PlayerChoice.DOUBLE
        self.game.save_choice(self.choice)
        self.game.player.add_card(self.game.deck.draw_card())
        if self.game.player.state is HandState.BUST:
            self.game.phase = GamePhase.END
        else:
            self.game.phase = GamePhase.DEALER
        await interaction.response.edit_message(embed=self.game.build_game_embed(), view=self)
        self.stop()

    @discord.ui.button(label='Surrender')
    async def surrender(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.game.is_betting:
            await interaction.response.send_message(f'You are not betting!',
                                                    ephemeral=True)
            return
        self.choice = PlayerChoice.SURRENDER
        self.game.save_choice(self.choice)
        await increase_balance(self.game.ctx, self.game.ctx.author, self.game.bet/2)
        self.stop()


    @discord.ui.button(label='Help', style=discord.ButtonStyle.grey, row=1)
    async def help(self, interaction: discord.Interaction, button: discord.ui.Button):
        help_message = '''
        __**Blackjack**__
        The main goal is to have your hand's value be closer to 21 than the dealer's, without going over 21.
        A hand's value is the sum of the card's values, with Ace being worth 1 or 11 and face cards worth 10.
        
        Actions
        ----------------
        **Hit**: Take another card to attempt to get closer to 21, or 21 exactly
        **Stand**: End your turn with no additional cards
        **Double**: Get only 1 card and double down your bet. Must be your first action
        **Surrender**: Forfeit half the bet and end the round immediately. Must be your first action
        
        Terminology
        ----------------
        **Bust**: Going over 21
        **Blackjack**: Hand value is exactly 21
        **Push**: Tie, bet is returned with no loss or gain
        **Natural**: Getting a Blackjack from the 2 cards dealt initially. Win 1.5x your bet
        **Soft hand**: When the player has the choice to count an Ace as 1 or 11 (Ex. A + 6 = Soft 17, value = 7 or 17)
        '''
        await interaction.response.send_message(dedent(help_message), ephemeral=True)

    async def on_timeout(self):
        self.choice = PlayerChoice.STAND
        self.game.save_choice(self.choice)
        await self.disable()
        self.stop()


class PlayAgainView(discord.ui.View):
    def __init__(self, *, game=None, embed=None):
        super().__init__(timeout=60)
        self.message = None
        self.game: Game = game
        self.embed = embed
        self.player = game.ctx.author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None:
            return False
        if interaction.user == self.player:
            return True
        else:
            await interaction.response.send_message('This game is not yours', ephemeral=True)
            return False

    @discord.ui.button(label='Play Again')
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.message:
            await interaction.response.edit_message(embed=self.embed, view=None)
        else:
            await interaction.response.defer()
        self.stop()
        await self.game.play_round(self.game.ctx, bet=self.game.original_bet)

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(embed=self.embed, view=None)


class Card:
    def __init__(self, value, suit):
        self.value = value
        self.suit = suit

    def __str__(self):
        return f'{self.value.name} of {self.suit.name}'

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.value is other.value

    def __add__(self, other):
        if isinstance(other, int):
            return self.value + other
        else:
            return self.value + other.value

    def __radd__(self, other):
        if isinstance(other, int):
            return self.value + other
        else:
            return self.__add__(other)

    @classmethod
    def ace(cls):
        return cls(CardValue.Ace, CardSuit.Spades)

    @property
    def display(self):
        return f'{display_cards[self.value.name]}{display_suits[self.suit.name]}'


class Deck:
    def __init__(self, decks=1):
        self.deck = [Card(value, suit)
                     for _ in range(decks) for value in CardValue for suit in CardSuit]
        self.shuffle()

    def shuffle(self):
        random.shuffle(self.deck)

    def draw_card(self):
        return self.deck.pop()

    def __len__(self):
        return len(self.deck)


class Hand:
    def __init__(self):
        self.cards = []
        self.value = 0
        self.is_soft = False
        self.state = HandState.PLAYING

    def calculate_hand(self):
        total = sum(self.cards)
        self.is_soft = False
        if Card.ace() in self.cards:
            for card in self.cards:
                if card.value is CardValue.Ace and total < 12:
                    total += 10
                    self.is_soft = True
        self.value = total
        if self.value == 21:
            self.state = HandState.BLACKJACK
        elif total > 21:
            self.state = HandState.BUST
        return self.value

    def add_card(self, card: Card):
        self.cards.append(card)
        self.calculate_hand()

    def is_blackjack(self):
        return self.value == 21

    @property
    def display(self):
        return f'{"Soft " if self.is_soft else ""}{self.calculate_hand()}'

    def __str__(self):
        value = 'Blackjack' if self.state is HandState.BLACKJACK else self.display
        return f'Cards: {" - ".join(c.display for c in self.cards)}\nValue: {value}'


class DealerHand(Hand):
    def __init__(self):
        super().__init__()
        self.state = HandState.HIDDEN

    def calculate_hand(self):
        self.value = super().calculate_hand()
        if self.state is HandState.HIDDEN:
            if self.cards[0].value is CardValue.Ace:
                self.is_soft = True
                return 11
            else:
                self.is_soft = False
                return self.cards[0].value
        return self.value

    def __str__(self):
        if self.state is HandState.HIDDEN:
            return f'Cards: {self.cards[0].display} - XX\nValue: {self.display}'
        return super().__str__()

    def reveal(self):
        if self.state is HandState.HIDDEN:
            self.state = HandState.PLAYING


class Game:
    def __init__(self, ctx, decks=4):
        self.num_decks = decks
        self.deck = Deck(decks)
        self.player = Hand()
        self.dealer = DealerHand()
        self.phase = GamePhase.IDLE
        self.ctx = ctx
        self.message = None
        self.is_playing = False
        self.bet: float = 0
        self.original_bet = 0
        self._choices = []

    @property
    def is_betting(self):
        return self.bet > 0

    def reset_deck(self):
        self.deck = Deck(self.num_decks)
        self.player = Hand()
        self.dealer = DealerHand()
        self.phase = GamePhase.IDLE
        self.message = None

    def reset_hands(self):
        self.message = None
        self.player = Hand()
        self.dealer = DealerHand()
        self.phase = GamePhase.IDLE

    def deal_cards(self):
        for _ in range(2):
            self.player.add_card(self.deck.draw_card())
            self.dealer.add_card(self.deck.draw_card())

    def save_choice(self, choice: PlayerChoice):
        choices = {PlayerChoice.HIT: 'H',
                   PlayerChoice.STAND: 'S',
                   PlayerChoice.DOUBLE: 'D',
                   PlayerChoice.SURRENDER: 'FF'}
        self._choices.append(choices[choice])

    def display_choices(self):
        if self._choices:
            return f'| Actions: {"".join(self._choices)}'
        return ''

    async def play_round(self, ctx: commands.Context, bet: float = 0):
        if self.is_playing:
            return
        self.is_playing = True
        self.ctx = ctx
        self.original_bet = self.bet = bet
        if self.is_betting:
            balance = await get_balance(ctx, ctx.author)
            if balance < bet:
                self.is_playing = False
                await self.ctx.send(f'{self.ctx.author.mention} you do not have enough money to bet ${bet:,.2f} (Balance: ${balance:,.2f})')
                return
            await decrease_balance(ctx, ctx.author, bet)

        self.deal_cards()
        self._choices = []
        if self.dealer.is_blackjack():
            self.message = await self.ctx.send(embed=self.build_game_embed())
            if self.player.is_blackjack():
                self.phase = GamePhase.END
            else:
                self.phase = GamePhase.DEALER_NATURAL
            await self.calculate_outcome()
            if len(self.deck) < 12:
                self.reset_deck()
            self.is_playing = False
            return
        elif self.player.is_blackjack():
            self.message = await self.ctx.send(embed=self.build_game_embed())
            self.phase = GamePhase.NATURAL
            await self.calculate_outcome()
            if len(self.deck) < 12:
                self.reset_deck()
            self.is_playing = False
            return
        view = BlackJackView(game=self)
        self.message = await self.ctx.send(embed=self.build_game_embed(), view=view)
        view.message = self.message
        self.phase = GamePhase.PLAYER
        await view.wait()
        if view.choice is PlayerChoice.SURRENDER:
            self.dealer.reveal()
            balance = await get_balance(self.ctx, self.ctx.author)
            description = f'You lost ${self.bet/2:,.2f} (Balance: ${balance:,.2f})'
            title = f'Blackjack | {self.ctx.author} | ${self.original_bet:,.2f}'

            embed = discord.Embed(title=title,
                                  description=description,
                                  color=0xff0000)
            embed.add_field(name='Your Hand', value=f'{self.player}\nResult: **Surrendered**')
            embed.add_field(name='Dealer\'s Hand', value=str(self.dealer))
            embed.set_footer(text=f'Cards remaining: {len(self.deck)} {self.display_choices()}')
            paview = PlayAgainView(game=self, embed=embed)
            end_msg = await self.message.edit(embed=embed, view=paview)
            view.message = end_msg
            self.reset_hands()
            self.is_playing = False
            return

        self.dealer.reveal()
        if self.phase is GamePhase.DEALER:
            if self.dealer.value >= 17:
                self.phase = GamePhase.END
            while self.dealer.value < 17:
                self.dealer.add_card(self.deck.draw_card())
            self.dealer.calculate_hand()
            self.phase = GamePhase.END
        await self.calculate_outcome()
        if len(self.deck) < 12:
            self.reset_deck()
        self.is_playing = False

    async def calculate_outcome(self):
        self.dealer.reveal()
        self.dealer.calculate_hand()
        if self.phase is GamePhase.NATURAL:
            embed = await self.result_embed(GameResult.NATURAL, 'Natural Blackjack')
        elif self.phase is GamePhase.DEALER_NATURAL:
            embed = await self.result_embed(GameResult.LOSS, 'Dealer Natural Blackjack')
        elif self.player.state is HandState.BUST:
            embed = await self.result_embed(GameResult.LOSS, 'Bust')
        elif self.dealer.state is HandState.BUST:
            embed = await self.result_embed(GameResult.WIN, 'Dealer Bust')
        elif self.dealer.value == self.player.value:
            embed = await self.result_embed(GameResult.TIE, 'Push')
        elif self.player.state is HandState.BLACKJACK:
            embed = await self.result_embed(GameResult.WIN, 'Blackjack')
        elif self.dealer.state is HandState.BLACKJACK:
            embed = await self.result_embed(GameResult.LOSS, 'Dealer Blackjack')
        elif self.player.value > self.dealer.value:
            embed = await self.result_embed(GameResult.WIN, 'Closer to 21')
        else:
            embed = await self.result_embed(GameResult.LOSS, 'Dealer closer to 21')
        view = PlayAgainView(game=self, embed=embed)
        end_msg = await self.message.edit(embed=embed, view=view)
        view.message = end_msg
        self.reset_hands()

    def build_game_embed(self):
        if self.is_betting:
            title = f'Blackjack | {self.ctx.author} | ${self.original_bet:,.2f}'
        else:
            title = f'Blackjack | {self.ctx.author}'

        embed = discord.Embed(title=title,
                              description='Press the buttons to play',
                              color=0xFFFFFE)
        embed.add_field(name='Your Hand', value=str(self.player))
        embed.add_field(name='Dealer\'s Hand', value=str(self.dealer))
        embed.set_footer(text=f'Cards remaining: {len(self.deck)} {self.display_choices()}')
        return embed

    async def result_embed(self, result, hand):
        results = {
            GameResult.WIN: ('You won', 0x55dd55),
            GameResult.NATURAL: ('You won', 0x55dd55),
            GameResult.LOSS: ('You lost', 0xff0000),
            GameResult.TIE: ('You tied', 0xFAA935)
        }
        description, colour = results[result]

        if self.is_betting:
            winnings, balance = await self.process_bet(result=result)
            if result is not GameResult.TIE:
                description += f' ${winnings:,.2f} (Balance: ${balance:,.2f})'
            else:
                description += f' Balance: ${balance:,.2f}'

        if self.is_betting:
            title = f'Blackjack | {self.ctx.author} | ${self.original_bet:,.2f}'
        else:
            title = f'Blackjack | {self.ctx.author}'
        embed = discord.Embed(title=title,
                              description=description,
                              color=colour)
        embed.add_field(name='Your Hand', value=f'{self.player}\nResult: **{hand}**')
        embed.add_field(name='Dealer\'s Hand', value=str(self.dealer))
        embed.set_footer(text=f'Cards remaining: {len(self.deck)} {self.display_choices()}')
        return embed

    async def process_bet(self, *, result: GameResult):
        if result is GameResult.WIN:
            out = self.bet
            amount = self.bet * 2
        elif result is GameResult.NATURAL:
            out = self.bet * 1.5
            amount = self.bet * 2.5
        elif result is GameResult.TIE:
            out = 0
            amount = self.bet
        elif result is GameResult.LOSS:
            out = self.bet
            amount = 0

        if amount > 0:
            await increase_balance(self.ctx, self.ctx.author, amount)
        return out, await get_balance(self.ctx, self.ctx.author)

