# SPDX-License-Identifier: GPL-3.0-or-later
"""Player profile persistence (bankroll, statistics and preferences)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields

from gi.repository import GLib

from .engine.game import Stats
from .engine.rules import Rules

ANIMATION_SPEEDS = {"off": 0.0, "fast": 0.55, "normal": 1.0, "slow": 1.6}


@dataclass
class Preferences:
    starting_bankroll: int = 1000
    animation_speed: str = "normal"
    show_totals: bool = True
    show_count: bool = False
    coach: bool = True
    card_back: str = "red"  # red | blue | green
    sound: bool = True

    @classmethod
    def from_dict(cls, data: dict | None) -> "Preferences":
        prefs = cls()
        for f in fields(cls):
            if data and f.name in data and isinstance(data[f.name], type(getattr(prefs, f.name))):
                setattr(prefs, f.name, data[f.name])
        if prefs.animation_speed not in ANIMATION_SPEEDS:
            prefs.animation_speed = "normal"
        builtin = ("red", "blue", "green", *PACK_BACKS)
        if prefs.card_back not in builtin and not prefs.card_back.startswith("custom:"):
            prefs.card_back = "red"
        return prefs


@dataclass
class Profile:
    bankroll: float = 1000
    rules: Rules = field(default_factory=Rules)
    prefs: Preferences = field(default_factory=Preferences)
    stats: Stats = field(default_factory=Stats)
    last_bet: int = 0


# Card backs designed by Hector "H4CK70R" Mejia, bundled in veintiuno/backs/<name>.jpg.
PACK_BACKS = (
    "h4ck70r", "hacker-oscuro", "cthulhu-abismal", "leviatan-abismal", "hidra-venenosa",
    "metalero-infernal", "gotico-oscuro", "gotico-vampirico", "gotico-polilla-mortuoria",
    "pesadilla-calabaza", "devorador-estrellas", "oraculo-vacio", "angel-entropia",
    "reina-aracnida-cosmica", "ojo-singularidad", "gusano-eclipse",
)


def backs_dir() -> str:
    """Folder holding the player's custom card back images."""
    return os.path.join(GLib.get_user_data_dir(), "veintiuno", "backs")


def list_custom_backs() -> list[str]:
    try:
        names = sorted(n for n in os.listdir(backs_dir()) if n.endswith(".png"))
    except OSError:
        return []
    return [f"custom:{n}" for n in names]


def _path() -> str:
    return os.path.join(GLib.get_user_data_dir(), "veintiuno", "profile.json")


def load() -> Profile:
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return Profile()
    if not isinstance(data, dict):
        return Profile()
    prefs = Preferences.from_dict(data.get("prefs"))
    try:
        bankroll = float(data.get("bankroll", prefs.starting_bankroll))
    except (TypeError, ValueError):
        bankroll = prefs.starting_bankroll
    try:
        last_bet = int(data.get("last_bet", 0))
    except (TypeError, ValueError):
        last_bet = 0
    return Profile(bankroll=bankroll,
                   rules=Rules.from_dict(data.get("rules")),
                   prefs=prefs,
                   stats=Stats.from_dict(data.get("stats")),
                   last_bet=last_bet)


def save(profile: Profile) -> None:
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "version": 1,
        "bankroll": profile.bankroll,
        "last_bet": profile.last_bet,
        "rules": profile.rules.to_dict(),
        "prefs": asdict(profile.prefs),
        "stats": profile.stats.to_dict(),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
