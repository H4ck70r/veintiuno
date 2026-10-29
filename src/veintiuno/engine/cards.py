# SPDX-License-Identifier: GPL-3.0-or-later
"""Cards, shoe and hands."""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field

SPADES, HEARTS, DIAMONDS, CLUBS = range(4)
SUITS = (SPADES, HEARTS, DIAMONDS, CLUBS)
RANKS = tuple(range(1, 14))  # 1 = ace, 11 = jack, 12 = queen, 13 = king
RANK_LABELS = {1: "A", 11: "J", 12: "Q", 13: "K"}

_ids = itertools.count(1)


@dataclass(eq=False)
class Card:
    rank: int
    suit: int
    face_up: bool = True
    id: int = field(default_factory=lambda: next(_ids))

    @property
    def value(self) -> int:
        """Blackjack value, counting aces as 1."""
        return min(self.rank, 10)

    @property
    def label(self) -> str:
        return RANK_LABELS.get(self.rank, str(self.rank))

    @property
    def is_red(self) -> bool:
        return self.suit in (HEARTS, DIAMONDS)

    def __repr__(self) -> str:
        return f"{self.label}{'♠♥♦♣'[self.suit]}"


def hand_total(cards) -> tuple[int, bool]:
    """Return (best total, is_soft) for the given cards."""
    total = sum(c.value for c in cards)
    if any(c.rank == 1 for c in cards) and total + 10 <= 21:
        return total + 10, True
    return total, False


class Shoe:
    """A shoe of one or more 52-card decks with a cut card."""

    def __init__(self, decks: int = 6, penetration: float = 0.75, rng: random.Random | None = None):
        self.decks = decks
        self.penetration = penetration
        self.rng = rng or random.SystemRandom()
        self.cards: list[Card] = []
        self.shuffle()

    def shuffle(self) -> None:
        self.cards = [Card(r, s) for _ in range(self.decks) for s in SUITS for r in RANKS]
        self.rng.shuffle(self.cards)
        self.cut = int(len(self.cards) * (1 - self.penetration))

    @property
    def size(self) -> int:
        return self.decks * 52

    @property
    def remaining(self) -> int:
        return len(self.cards)

    @property
    def needs_shuffle(self) -> bool:
        return len(self.cards) <= self.cut

    def draw(self, face_up: bool = True) -> Card:
        if not self.cards:
            # Never run dry mid-round: start a fresh shoe.
            self.shuffle()
        card = self.cards.pop()
        card.face_up = face_up
        return card

    def stack(self, cards: list[Card]) -> None:
        """Put cards on top of the shoe, the first one drawn first (for tests)."""
        self.cards.extend(reversed(cards))


class Hand:
    def __init__(self, bet: float = 0, split_depth: int = 0):
        self.cards: list[Card] = []
        self.bet = bet
        self.split_depth = split_depth
        self.split_aces = False
        self.doubled = False
        self.surrendered = False
        self.stood = False
        self.result: str | None = None
        self.payout: float = 0  # amount returned to the player, stake included

    @property
    def total(self) -> int:
        return hand_total(self.cards)[0]

    @property
    def soft(self) -> bool:
        return hand_total(self.cards)[1]

    @property
    def is_split(self) -> bool:
        return self.split_depth > 0

    @property
    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and self.total == 21 and not self.is_split

    @property
    def busted(self) -> bool:
        return self.total > 21

    @property
    def is_pair(self) -> bool:
        return len(self.cards) == 2 and self.cards[0].rank == self.cards[1].rank

    @property
    def done(self) -> bool:
        return self.stood or self.busted or self.surrendered or self.total == 21

    def __repr__(self) -> str:
        return f"Hand({self.cards}, total={self.total}, bet={self.bet})"
