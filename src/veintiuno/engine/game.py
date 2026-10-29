# SPDX-License-Identifier: GPL-3.0-or-later
"""The blackjack table state machine.

The game resolves every step instantly; the UI animates the result by
looking at the order in which cards were dealt (`seq_of`).
"""

from __future__ import annotations

import itertools
import random
from dataclasses import asdict, dataclass, fields

from .cards import Card, Hand, Shoe, hand_total
from .rules import Rules
from .strategy import DOUBLE, HIT, SPLIT, STAND, SURRENDER, Counter, recommend

BETTING = "betting"
INSURANCE = "insurance"
PLAYER = "player"
ROUND_OVER = "round-over"

BLACKJACK = "blackjack"
WIN = "win"
LOSE = "lose"
PUSH = "push"
BUST = "bust"
SURRENDERED = "surrender"


@dataclass
class Stats:
    rounds: int = 0
    hands: int = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    blackjacks: int = 0
    busts: int = 0
    surrenders: int = 0
    doubles: int = 0
    doubles_won: int = 0
    splits: int = 0
    insurance_taken: int = 0
    insurance_won: int = 0
    dealer_blackjacks: int = 0
    dealer_busts: int = 0
    net: float = 0
    total_wagered: float = 0
    biggest_win: float = 0
    biggest_loss: float = 0
    peak_bankroll: float = 0
    rebuys: int = 0
    decisions: int = 0
    correct_decisions: int = 0
    best_streak: int = 0
    current_streak: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Stats":
        stats = cls()
        for f in fields(cls):
            if data and f.name in data:
                try:
                    setattr(stats, f.name, type(getattr(stats, f.name))(data[f.name]))
                except (TypeError, ValueError):
                    pass
        return stats


@dataclass
class Mistake:
    action: str
    advice: str


class Game:
    def __init__(self, rules: Rules | None = None, bankroll: float = 1000,
                 stats: Stats | None = None, rng: random.Random | None = None):
        self.rules = rules or Rules()
        self._pending_rules: Rules | None = None
        self.rng = rng
        self.shoe = Shoe(self.rules.decks, self.rules.penetration, rng)
        self.counter = Counter()
        self.bankroll = float(bankroll)
        self.stats = stats or Stats()
        self.stats.peak_bankroll = max(self.stats.peak_bankroll, self.bankroll)
        self.phase = BETTING
        self.bet = 0
        self.last_bet = 0
        self.hands: list[Hand] = []
        self.dealer = Hand()
        self.active = 0
        self.insurance_bet = 0.0
        self.insurance_result: str | None = None
        self.round_net = 0.0
        self.just_shuffled = False
        self.last_mistake: Mistake | None = None
        self._seq = itertools.count(1)
        self.seq_of: dict[int, int] = {}
        self.reveal_seq = 0

    # -- rules ---------------------------------------------------------

    def set_rules(self, rules: Rules) -> None:
        """Change the table rules; takes effect at the next deal."""
        if self.phase == BETTING:
            self._apply_rules(rules)
        else:
            self._pending_rules = rules

    def _apply_rules(self, rules: Rules) -> None:
        reshoe = rules.decks != self.rules.decks or rules.penetration != self.rules.penetration
        self.rules = rules
        self._pending_rules = None
        if reshoe:
            self.shoe = Shoe(rules.decks, rules.penetration, self.rng)
            self.counter.reset()
            self.just_shuffled = True
        self.bet = min(self.bet, self.max_bet)

    # -- betting -------------------------------------------------------

    @property
    def max_bet(self) -> int:
        return int(min(self.rules.max_bet, self.bankroll))

    def add_chip(self, amount: int) -> bool:
        if self.phase != BETTING or self.bet + amount > self.max_bet:
            return False
        self.bet += amount
        return True

    def clear_bet(self) -> None:
        if self.phase == BETTING:
            self.bet = 0

    def can_rebet(self) -> bool:
        return self.phase == BETTING and self.rules.min_bet <= self.last_bet <= self.max_bet

    def rebet(self) -> bool:
        if not self.can_rebet():
            return False
        self.bet = self.last_bet
        return True

    @property
    def can_deal(self) -> bool:
        return self.phase == BETTING and self.rules.min_bet <= self.bet <= self.max_bet

    @property
    def is_broke(self) -> bool:
        return self.phase == BETTING and self.bankroll < self.rules.min_bet

    def rebuy(self, amount: float) -> None:
        self.bankroll += amount
        self.stats.rebuys += 1
        self.stats.peak_bankroll = max(self.stats.peak_bankroll, self.bankroll)

    @property
    def money_on_table(self) -> float:
        """Stakes not yet settled (refunded if the game is closed mid-round)."""
        if self.phase in (INSURANCE, PLAYER):
            return sum(h.bet for h in self.hands) + self.insurance_bet
        return 0.0

    # -- dealing -------------------------------------------------------

    def _deal_to(self, hand: Hand, face_up: bool = True) -> Card:
        card = self.shoe.draw(face_up)
        hand.cards.append(card)
        self.seq_of[card.id] = next(self._seq)
        self.counter.observe(card)
        return card

    def deal(self) -> bool:
        if not self.can_deal:
            return False
        if self._pending_rules:
            self._apply_rules(self._pending_rules)
            if not self.can_deal:
                return False
        if self.shoe.needs_shuffle:
            self.shoe.shuffle()
            self.counter.reset()
            self.just_shuffled = True

        self.bankroll -= self.bet
        self.last_bet = self.bet
        self.hands = [Hand(self.bet)]
        self.dealer = Hand()
        self.active = 0
        self.insurance_bet = 0.0
        self.insurance_result = None
        self.round_net = 0.0
        self.last_mistake = None
        self.seq_of.clear()
        self.reveal_seq = 0

        player = self.hands[0]
        self._deal_to(player)
        self._deal_to(self.dealer)
        self._deal_to(player)
        if self.rules.dealer_peek:
            self._deal_to(self.dealer, face_up=False)

        if (self.rules.insurance and self.dealer.cards[0].rank == 1
                and self.bankroll >= player.bet / 2):
            self.phase = INSURANCE
            return True
        self._after_insurance()
        return True

    @property
    def insurance_cost(self) -> float:
        return self.hands[0].bet / 2 if self.hands else 0

    def insurance(self, take: bool) -> None:
        if self.phase != INSURANCE:
            return
        if take:
            self.insurance_bet = self.insurance_cost
            self.bankroll -= self.insurance_bet
            self.stats.insurance_taken += 1
        self._after_insurance()

    def _after_insurance(self) -> None:
        if self.rules.dealer_peek and self.dealer.cards[0].value in (1, 10) and self.dealer.is_blackjack:
            self._finish_round()
            return
        if self.hands[0].is_blackjack:
            self._finish_round()
            return
        self.phase = PLAYER
        self._advance()

    # -- player decisions ---------------------------------------------

    @property
    def current_hand(self) -> Hand | None:
        if self.phase == PLAYER and self.active < len(self.hands):
            return self.hands[self.active]
        return None

    def can_hit(self) -> bool:
        hand = self.current_hand
        return hand is not None and not hand.done

    def can_stand(self) -> bool:
        return self.can_hit()

    def can_double(self) -> bool:
        hand = self.current_hand
        if hand is None or hand.done or len(hand.cards) != 2 or hand.split_aces:
            return False
        if hand.is_split and not self.rules.double_after_split:
            return False
        return self.bankroll >= hand.bet and self.rules.can_double_total(hand.total)

    def can_split(self) -> bool:
        hand = self.current_hand
        if hand is None or hand.done or len(hand.cards) != 2:
            return False
        a, b = hand.cards
        same = a.rank == b.rank or (self.rules.split_unlike_tens and a.value == b.value == 10)
        if not same or len(self.hands) >= self.rules.max_hands or self.bankroll < hand.bet:
            return False
        if a.rank == 1 and hand.split_aces and not self.rules.resplit_aces:
            return False
        return True

    def can_surrender(self) -> bool:
        hand = self.current_hand
        return (hand is not None and self.rules.late_surrender and len(self.hands) == 1
                and len(hand.cards) == 2 and not hand.is_split and not hand.done)

    def advice(self) -> str | None:
        hand = self.current_hand
        if hand is None or hand.done:
            return None
        return recommend(hand.cards, self.dealer.cards[0], self.rules,
                         can_double=self.can_double(), can_split=self.can_split(),
                         can_surrender=self.can_surrender())

    def _record_decision(self, action: str) -> None:
        advice = self.advice()
        self.stats.decisions += 1
        if advice == action:
            self.stats.correct_decisions += 1
            self.last_mistake = None
        else:
            self.last_mistake = Mistake(action, advice)

    def hit(self) -> bool:
        if not self.can_hit():
            return False
        self._record_decision(HIT)
        self._deal_to(self.current_hand)
        self._advance()
        return True

    def stand(self) -> bool:
        if not self.can_stand():
            return False
        self._record_decision(STAND)
        self.current_hand.stood = True
        self._advance()
        return True

    def double(self) -> bool:
        if not self.can_double():
            return False
        self._record_decision(DOUBLE)
        hand = self.current_hand
        self.bankroll -= hand.bet
        hand.bet *= 2
        hand.doubled = True
        self.stats.doubles += 1
        self._deal_to(hand)
        hand.stood = True
        self._advance()
        return True

    def split(self) -> bool:
        if not self.can_split():
            return False
        self._record_decision(SPLIT)
        hand = self.current_hand
        self.bankroll -= hand.bet
        self.stats.splits += 1
        hand.split_depth += 1
        twin = Hand(hand.bet, hand.split_depth)
        twin.cards.append(hand.cards.pop())
        if hand.cards[0].rank == 1:
            hand.split_aces = twin.split_aces = True
        self.hands.insert(self.active + 1, twin)
        self._deal_to(hand)
        self._check_split_aces(hand)
        self._advance()
        return True

    def surrender(self) -> bool:
        if not self.can_surrender():
            return False
        self._record_decision(SURRENDER)
        self.current_hand.surrendered = True
        self._advance()
        return True

    def _check_split_aces(self, hand: Hand) -> None:
        if not hand.split_aces or self.rules.hit_split_aces:
            return
        could_resplit = (self.rules.resplit_aces and hand.cards[-1].rank == 1
                         and len(self.hands) < self.rules.max_hands)
        if not could_resplit:
            hand.stood = True

    def _advance(self) -> None:
        while self.active < len(self.hands):
            hand = self.hands[self.active]
            if len(hand.cards) == 1:
                self._deal_to(hand)
                self._check_split_aces(hand)
            if not hand.done:
                self.phase = PLAYER
                return
            self.active += 1
        self._finish_round()

    # -- dealer and settlement ----------------------------------------

    def _finish_round(self) -> None:
        for card in self.dealer.cards:
            if not card.face_up:
                card.face_up = True
                self.reveal_seq = next(self._seq)
                self.counter.observe(card)
        if len(self.dealer.cards) == 1:
            self._deal_to(self.dealer)

        live = [h for h in self.hands if not h.busted and not h.surrendered]
        must_play = any(not h.is_blackjack for h in live)
        if must_play and not self.dealer.is_blackjack:
            while self._dealer_draws():
                self._deal_to(self.dealer)
        self._settle()

    def _dealer_draws(self) -> bool:
        total, soft = self.dealer.total, self.dealer.soft
        return total < 17 or (total == 17 and soft and self.rules.dealer_hits_soft17)

    def _settle(self) -> None:
        dealer = self.dealer
        dealer_bj = dealer.is_blackjack
        stats = self.stats
        staked = 0.0
        returned = 0.0

        if self.insurance_bet:
            staked += self.insurance_bet
            if dealer_bj:
                self.insurance_result = WIN
                returned += self.insurance_bet * 3
                stats.insurance_won += 1
            else:
                self.insurance_result = LOSE

        for hand in self.hands:
            staked += hand.bet
            if hand.surrendered:
                hand.result, hand.payout = SURRENDERED, hand.bet / 2
            elif hand.busted:
                hand.result, hand.payout = BUST, 0
            elif hand.is_blackjack and not dealer_bj:
                hand.result, hand.payout = BLACKJACK, hand.bet * (1 + self.rules.blackjack_ratio)
            elif dealer_bj:
                hand.result, hand.payout = (PUSH, hand.bet) if hand.is_blackjack else (LOSE, 0)
            elif dealer.busted or hand.total > dealer.total:
                hand.result, hand.payout = WIN, hand.bet * 2
            elif hand.total == dealer.total:
                hand.result, hand.payout = PUSH, hand.bet
            else:
                hand.result, hand.payout = LOSE, 0
            returned += hand.payout

            stats.hands += 1
            if hand.result in (WIN, BLACKJACK):
                stats.wins += 1
                stats.current_streak = max(stats.current_streak, 0) + 1
                stats.best_streak = max(stats.best_streak, stats.current_streak)
                if hand.doubled:
                    stats.doubles_won += 1
            elif hand.result == PUSH:
                stats.pushes += 1
            else:
                stats.losses += 1
                stats.current_streak = 0
            stats.blackjacks += hand.result == BLACKJACK
            stats.busts += hand.result == BUST
            stats.surrenders += hand.result == SURRENDERED

        self.bankroll = round(self.bankroll + returned, 2)
        self.round_net = round(returned - staked, 2)
        stats.rounds += 1
        stats.dealer_blackjacks += dealer_bj
        stats.dealer_busts += dealer.busted
        stats.total_wagered += staked
        stats.net = round(stats.net + self.round_net, 2)
        stats.biggest_win = max(stats.biggest_win, self.round_net)
        stats.biggest_loss = max(stats.biggest_loss, -self.round_net)
        stats.peak_bankroll = max(stats.peak_bankroll, self.bankroll)
        self.phase = ROUND_OVER

    def new_round(self) -> None:
        if self.phase != ROUND_OVER:
            return
        self.phase = BETTING
        self.hands = []
        self.dealer = Hand()
        self.active = 0
        self.insurance_bet = 0.0
        self.insurance_result = None
        self.bet = 0
        if self._pending_rules:
            self._apply_rules(self._pending_rules)

    # -- info ----------------------------------------------------------

    @property
    def dealer_visible_total(self) -> int | None:
        visible = [c for c in self.dealer.cards if c.face_up]
        if not visible:
            return None
        return hand_total(visible)[0]

    def true_count(self) -> float:
        return self.counter.true_count(self.shoe.remaining)
