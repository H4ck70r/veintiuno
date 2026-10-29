# SPDX-License-Identifier: GPL-3.0-or-later
from gettext import gettext as _

from ..engine.game import BLACKJACK, BUST, LOSE, PUSH, SURRENDERED, WIN
from ..engine.strategy import DOUBLE, HIT, SPLIT, STAND, SURRENDER


def money(amount: float, signed: bool = False) -> str:
    sign = ""
    if amount < 0:
        sign = "−"
    elif signed and amount > 0:
        sign = "+"
    amount = abs(amount)
    if amount != int(amount):
        text = f"{amount:,.2f}"
    else:
        text = f"{int(amount):,}"
    return f"{sign}${text}"


def action_name(action: str | None) -> str:
    return {
        HIT: _("Hit"),
        STAND: _("Stand"),
        DOUBLE: _("Double"),
        SPLIT: _("Split"),
        SURRENDER: _("Surrender"),
    }.get(action, "")


def result_name(result: str | None) -> str:
    return {
        BLACKJACK: _("Blackjack!"),
        WIN: _("Win"),
        LOSE: _("Lose"),
        PUSH: _("Push"),
        BUST: _("Bust"),
        SURRENDERED: _("Surrendered"),
    }.get(result, "")
