import discord
import asyncio
import random
from itertools import islice
from aenum import Enum, IntEnum, NoAlias


class CardValue(IntEnum, settings=NoAlias):
    SAce  = 11
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
    DEALER_NATURAL= 6


display_cards = {
    'SAce':  'A',
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

class Card:
    def __init__(self, value, suit):
        self.value = value
        self.suit = suit

    def __str__(self):
        return f'{self.value.name} of {self.suit.name}'

    def __eq__(self, other):
        if not isinstance(other, Card):
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
    def is_soft(self):
        return self.value is CardValue.SAce

    @property
    def display(self):
        return f'{display_cards[self.value.name]}{display_suits[self.suit.name]}'


class Deck:
    def __init__(self, decks=1):
        self.deck = [Card(value, suit)
                     for _ in range(decks) for value in islice(CardValue, 1, None) for suit in CardSuit]
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
                    card.value = CardValue.SAce
                    total = sum(self.cards)
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
        return f'Cards: {" - ".join(c.display for c in self.cards)}.\nValue: {value}'


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
                return self.cards[0].value
        return self.value

    def __str__(self):
        if self.state is HandState.HIDDEN:
            return f'Cards: {self.cards[0].display} - XX.\nValue: {self.display}'
        return super().__str__()

    def reveal(self):
        self.state = HandState.PLAYING


class Game:
    def __init__(self, ctx, decks=4):
        self.deck = Deck(decks)
        self.player = Hand()
        self.dealer = DealerHand()
        self.phase = GamePhase.IDLE
        self.ctx = ctx
        self.message = None

    def deal_cards(self):
        for _ in range(2):
            self.player.add_card(self.deck.draw_card())
            # self.dealer.add_card(self.deck.draw_card())
        self.dealer.add_card(Card.ace())
        self.dealer.add_card(Card(CardValue.Jack, CardSuit.Clubs))

    async def play_round(self, ctx):
        self.ctx = ctx
        self.deal_cards()
        self.message = await self.ctx.send(embed=self.build_game_embed())
        if self.dealer.is_blackjack():
            if self.player.is_blackjack():
                self.phase = GamePhase.END
            else:
                self.phase = GamePhase.DEALER_NATURAL
            return
        elif self.player.is_blackjack():
            self.phase = GamePhase.NATURAL
            return

        self.phase = GamePhase.PLAYER
        reactions = ['👇', '🛑']
        [await self.message.add_reaction(r) for r in reactions]
        def check(r, u):
            return str(r) in reactions and u == self.ctx.author and r.message == self.message

        while self.phase is GamePhase.PLAYER:
            try:
                reaction, _ = await self.ctx.bot.wait_for('reaction_add', check=check, timeout=3600)
            except asyncio.TimeoutError:
                choice = '🛑'
            else:
                choice = str(reaction)
            if choice == '👇':
                self.player.add_card(self.deck.draw_card())
                if self.player.state is HandState.BUST:
                    self.phase = GamePhase.END
                    break
                if self.player.state is HandState.BLACKJACK:
                    self.phase = GamePhase.DEALER
                    break
                await self.message.edit(embed=self.build_game_embed())
                await self.message.remove_reaction('👇', self.ctx.author)
            elif choice == '🛑':
                self.phase = GamePhase.DEALER
                break

        self.dealer.reveal()
        if self.phase is GamePhase.DEALER:
            if self.dealer.value >= 17:
                self.phase = GamePhase.END
            while self.dealer.value < 17 and not self.dealer.is_soft:
                self.dealer.add_card(self.deck.draw_card())
            self.dealer.calculate_hand()
            self.phase = GamePhase.END

    async def calculate_outcome(self):
        if self.phase is GamePhase.NATURAL:
            embed = self.result_embed('win', 'Natural Blackjack')
        elif self.phase is GamePhase.DEALER_NATURAL:
            embed = self.result_embed('lose', 'Dealer Natural Blackjack')
        elif self.player.state is HandState.BUST:
            embed = self.result_embed('lose', 'Bust')
        elif self.dealer.state is HandState.BUST:
            embed = self.result_embed('win', 'Dealer Bust')
        elif self.dealer.value == self.player.value:
            embed = self.result_embed('tie', 'Push')
        elif self.player.state is HandState.BLACKJACK:
            embed = self.result_embed('win', 'Blackjack')
        elif self.dealer.state is HandState.BLACKJACK:
            embed = self.result_embed('lose', 'Dealer Blackjack')
        elif self.player.value > self.dealer.value:
            embed = self.result_embed('win', 'Closer to 21')
        else:
            embed = self.result_embed('lose', 'Dealer closer to 21')
        await self.message.edit(embed=embed)
        self.reset_hands()

    def build_game_embed(self):
        embed = discord.Embed(title=f'Blackjack | {self.ctx.author}',
                              description='Press 👇 to Hit (draw another card) or 🛑 to Stand (end turn)',
                              color=0xFFFFFE)
        embed.add_field(name='Your Hand', value=str(self.player))
        embed.add_field(name='Dealer\'s Hand', value=str(self.dealer))
        embed.set_footer(text=f'Cards remaining: {len(self.deck)}')
        return embed

    def result_embed(self, result, hand):
        results = {
            'win': ('You won', 0x55dd55),
            'lose': ('You lost', 0xff0000),
            'tie': ('You tied', 0xFAA935)
        }
        description, colour = results[result]

        embed = discord.Embed(title=f'Blackjack | {self.ctx.author}',
                              description=description,
                              color=colour)
        embed.add_field(name='Your Hand', value=f'{self.player}\nResult: {hand}')
        embed.add_field(name='Dealer\'s Hand', value=str(self.dealer))
        embed.set_footer(text=f'Cards remaining: {len(self.deck)}')
        return embed

    def reset_hands(self):
        self.message = None
        self.player = Hand()
        self.dealer = DealerHand()
        self.phase = GamePhase.IDLE




