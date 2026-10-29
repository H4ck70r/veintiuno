# SPDX-License-Identifier: GPL-3.0-or-later
"""Table rules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

DOUBLE_ANY = "any"
DOUBLE_9_11 = "9-11"
DOUBLE_10_11 = "10-11"


@dataclass
class Rules:
    decks: int = 6
    penetration: float = 0.75
    dealer_hits_soft17: bool = False
    blackjack_pays: str = "3:2"  # or "6:5"
    double_on: str = DOUBLE_ANY
    double_after_split: bool = True
    max_hands: int = 4
    resplit_aces: bool = False
    hit_split_aces: bool = False
    split_unlike_tens: bool = True
    late_surrender: bool = True
    insurance: bool = True
    dealer_peek: bool = True  # False = European no-hole-card game
    min_bet: int = 5
    max_bet: int = 1000

    @property
    def blackjack_ratio(self) -> float:
        num, den = self.blackjack_pays.split(":")
        return int(num) / int(den)

    def can_double_total(self, total: int) -> bool:
        if self.double_on == DOUBLE_9_11:
            return 9 <= total <= 11
        if self.double_on == DOUBLE_10_11:
            return 10 <= total <= 11
        return True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Rules":
        rules = cls()
        if not data:
            return rules
        for f in fields(cls):
            if f.name in data:
                value = data[f.name]
                default = getattr(rules, f.name)
                try:
                    value = type(default)(value)
                except (TypeError, ValueError):
                    continue
                setattr(rules, f.name, value)
        rules.decks = max(1, min(8, rules.decks))
        rules.max_hands = max(2, min(4, rules.max_hands))
        rules.penetration = max(0.5, min(0.9, rules.penetration))
        if rules.blackjack_pays not in ("3:2", "6:5"):
            rules.blackjack_pays = "3:2"
        if rules.double_on not in (DOUBLE_ANY, DOUBLE_9_11, DOUBLE_10_11):
            rules.double_on = DOUBLE_ANY
        rules.min_bet = max(1, rules.min_bet)
        rules.max_bet = max(rules.min_bet, rules.max_bet)
        return rules

    def house_edge(self) -> float:
        """Approximate house edge in percent for perfect basic strategy.

        Uses the usual published rule-effect approximations, relative to a
        single deck, S17, 3:2, DAS-less, no-surrender baseline.
        """
        edge = 0.0
        edge += {1: -0.01, 2: 0.32, 3: 0.43, 4: 0.48, 5: 0.52, 6: 0.54, 7: 0.56, 8: 0.57}[self.decks]
        if self.dealer_hits_soft17:
            edge += 0.20
        if self.blackjack_pays == "6:5":
            edge += 1.39
        if self.double_on == DOUBLE_9_11:
            edge += 0.09
        elif self.double_on == DOUBLE_10_11:
            edge += 0.18
        if self.double_after_split:
            edge -= 0.14
        if self.max_hands <= 2:
            edge += 0.05
        if self.resplit_aces:
            edge -= 0.08
        if self.hit_split_aces:
            edge -= 0.19
        if self.late_surrender:
            edge -= 0.07 if not self.dealer_hits_soft17 else 0.09
        if not self.dealer_peek:
            edge += 0.11
        return edge
