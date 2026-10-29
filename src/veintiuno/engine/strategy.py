# SPDX-License-Identifier: GPL-3.0-or-later
"""Basic strategy advisor and Hi-Lo card counting."""

from __future__ import annotations

from .cards import Card, hand_total
from .rules import Rules

HIT = "hit"
STAND = "stand"
DOUBLE = "double"
SPLIT = "split"
SURRENDER = "surrender"


def _hard(total: int, up: int, rules: Rules) -> str:
    h17 = rules.dealer_hits_soft17
    few_decks = rules.decks <= 2
    if total >= 17:
        return "Rs" if total == 17 and up == 11 and h17 else "S"
    if total == 16:
        if up <= 6:
            return "S"
        return "Rh" if up >= 9 else "H"
    if total == 15:
        if up <= 6:
            return "S"
        return "Rh" if up == 10 or (up == 11 and h17) else "H"
    if total in (13, 14):
        return "S" if up <= 6 else "H"
    if total == 12:
        return "S" if 4 <= up <= 6 else "H"
    if total == 11:
        return "H" if up == 11 and not h17 and not few_decks else "D"
    if total == 10:
        return "D" if up <= 9 else "H"
    if total == 9:
        return "D" if (3 if not few_decks else 2) <= up <= 6 else "H"
    return "H"


def _soft(total: int, up: int, rules: Rules) -> str:
    h17 = rules.dealer_hits_soft17
    if total >= 20:
        return "S"
    if total == 19:
        return "Ds" if up == 6 and h17 else "S"
    if total == 18:
        if up <= 6:
            return "S" if up == 2 and not h17 else "Ds"
        return "S" if up <= 8 else "H"
    if total == 17:
        return "D" if 3 <= up <= 6 else "H"
    if total in (15, 16):
        return "D" if 4 <= up <= 6 else "H"
    if total in (13, 14):
        return "D" if 5 <= up <= 6 else "H"
    return "H"


def _pair(value: int, up: int, rules: Rules) -> str | None:
    das = rules.double_after_split
    h17 = rules.dealer_hits_soft17
    if value == 1:
        return "P"
    if value == 10 or value == 5:
        return None
    if value == 9:
        return "P" if up in (2, 3, 4, 5, 6, 8, 9) else None
    if value == 8:
        return "Rp" if up == 11 and h17 else "P"
    if value == 7:
        return "P" if up <= 7 else None
    if value == 6:
        return "P" if (2 if das else 3) <= up <= 6 else None
    if value == 4:
        return "P" if das and up in (5, 6) else None
    # 2s and 3s
    return "P" if (2 if das else 4) <= up <= 7 else None


def upcard_value(card: Card) -> int:
    return 11 if card.rank == 1 else card.value


def recommend(cards: list[Card], dealer_up: Card, rules: Rules, *,
              can_double: bool, can_split: bool, can_surrender: bool) -> str:
    """Return the basic-strategy action for the given hand."""
    up = upcard_value(dealer_up)
    if can_split and len(cards) == 2 and cards[0].value == cards[1].value:
        code = _pair(cards[0].value, up, rules)
        if code == "Rp":
            return SURRENDER if can_surrender else SPLIT
        if code == "P":
            return SPLIT

    total, soft = hand_total(cards)
    code = _soft(total, up, rules) if soft else _hard(total, up, rules)
    if code == "D":
        return DOUBLE if can_double else HIT
    if code == "Ds":
        return DOUBLE if can_double else STAND
    if code == "Rh":
        return SURRENDER if can_surrender else HIT
    if code == "Rs":
        return SURRENDER if can_surrender else STAND
    return STAND if code == "S" else HIT


HI_LO = {1: -1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 0, 8: 0, 9: 0, 10: -1, 11: -1, 12: -1, 13: -1}


class Counter:
    """Hi-Lo running and true count over the cards the player has seen."""

    def __init__(self):
        self.running = 0
        self.seen: set[int] = set()

    def reset(self) -> None:
        self.running = 0
        self.seen.clear()

    def observe(self, card: Card) -> None:
        if card.face_up and card.id not in self.seen:
            self.seen.add(card.id)
            self.running += HI_LO[card.rank]

    def true_count(self, cards_remaining: int) -> float:
        decks_left = max(cards_remaining / 52, 0.5)
        return self.running / decks_left
