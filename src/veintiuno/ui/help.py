# SPDX-License-Identifier: GPL-3.0-or-later
"""How-to-play and keyboard shortcuts dialogs."""

from __future__ import annotations

from gettext import gettext as _

from gi.repository import Adw, Gtk


class _PageDialog(Adw.Dialog):
    def __init__(self, title):
        super().__init__(title=title, content_width=520, content_height=620)
        self.page = Adw.PreferencesPage()
        view = Adw.ToolbarView(content=self.page)
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)

    def group(self, title, description=None):
        group = Adw.PreferencesGroup(title=title, description=description or "")
        self.page.add(group)
        return group


class ShortcutsDialog(_PageDialog):
    def __init__(self):
        super().__init__(_("Keyboard Shortcuts"))
        sections = [
            (_("Betting"), [
                ("1 – 6", _("Add a 1, 5, 25, 100, 500 or 1,000 chip")),
                ("B", _("Rebet")),
                (_("Backspace"), _("Clear bet / change bet")),
                (_("Enter or Space"), _("Deal / rebet and deal")),
            ]),
            (_("Playing"), [
                ("H", _("Hit")),
                ("S", _("Stand")),
                ("D", _("Double")),
                ("P", _("Split")),
                ("R", _("Surrender")),
                ("Y / N", _("Take or decline insurance")),
                ("? / F1", _("Basic strategy hint")),
            ]),
            (_("General"), [
                ("Ctrl+N", _("New game")),
                ("Ctrl+I", _("Statistics")),
                ("Ctrl+,", _("Preferences")),
                ("Ctrl+?", _("Keyboard shortcuts")),
                ("Ctrl+Q", _("Quit")),
            ]),
        ]
        for title, rows in sections:
            group = self.group(title)
            for keys, action in rows:
                row = Adw.ActionRow(title=action)
                label = Gtk.Label(label=keys, css_classes=["dim-label", "monospace"])
                row.add_suffix(label)
                group.add(row)


class HelpDialog(_PageDialog):
    def __init__(self):
        super().__init__(_("How to Play"))
        sections = [
            (_("Goal"), _(
                "Beat the dealer by finishing closer to 21 without going over. "
                "Number cards count their value, faces count 10 and aces count 1 or 11.")),
            (_("Blackjack"), _(
                "An ace with a ten-value card as your first two cards is a blackjack. "
                "It pays 3 to 2 (or 6 to 5 if the table says so) unless the dealer also has one.")),
            (_("Your Options"), _(
                "Hit takes another card. Stand keeps your total. Double doubles your bet and "
                "gives you exactly one more card. Split turns a pair into two hands with a bet "
                "each. Surrender gives up the hand and returns half the bet; it is only "
                "available as your first decision.")),
            (_("Insurance"), _(
                "When the dealer shows an ace you may bet half your wager that the dealer has "
                "blackjack. It pays 2 to 1. Basic strategy never takes insurance.")),
            (_("The Dealer"), _(
                "The dealer has no choices: draws until reaching 17 or more, and on some tables "
                "also hits a soft 17 (a 17 counting an ace as 11).")),
            (_("Training"), _(
                "Turn on the strategy coach to be told when a play differs from basic strategy, "
                "press ? for a hint, and enable the card count to practise Hi-Lo counting: "
                "2–6 count +1, 7–9 count 0, tens and aces count −1. The true count is the "
                "running count divided by the decks left in the shoe.")),
        ]
        for title, text in sections:
            group = self.group(title)
            label = Gtk.Label(label=text, wrap=True, xalign=0)
            group.add(label)
