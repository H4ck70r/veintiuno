# SPDX-License-Identifier: GPL-3.0-or-later
"""Statistics dialog."""

from __future__ import annotations

from gettext import gettext as _

from gi.repository import Adw, Gtk

from ..engine.game import Stats
from .format import money


def _pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "—"


class StatsDialog(Adw.Dialog):
    def __init__(self, stats: Stats, on_reset):
        super().__init__(title=_("Statistics"), content_width=460, content_height=640)
        self._on_reset = on_reset

        header = Adw.HeaderBar()
        reset = Gtk.Button(label=_("_Reset"), use_underline=True)
        reset.add_css_class("destructive-action")
        reset.connect("clicked", self._confirm_reset)
        header.pack_start(reset)

        self.page = Adw.PreferencesPage()
        self._fill(stats)

        view = Adw.ToolbarView(content=self.page)
        view.add_top_bar(header)
        self.set_child(view)

    def _group(self, title, rows):
        group = Adw.PreferencesGroup(title=title)
        for label, value in rows:
            row = Adw.ActionRow(title=label)
            suffix = Gtk.Label(label=value, css_classes=["numeric", "dim-label"])
            row.add_suffix(suffix)
            group.add(row)
        self.page.add(group)
        return group

    def _fill(self, s: Stats) -> None:
        self._groups = [
            self._group(_("Results"), [
                (_("Rounds Played"), f"{s.rounds:,}"),
                (_("Hands Played"), f"{s.hands:,}"),
                (_("Won"), f"{s.wins:,} ({_pct(s.wins, s.hands)})"),
                (_("Lost"), f"{s.losses:,} ({_pct(s.losses, s.hands)})"),
                (_("Pushed"), f"{s.pushes:,} ({_pct(s.pushes, s.hands)})"),
                (_("Best Winning Streak"), f"{s.best_streak:,}"),
            ]),
            self._group(_("Money"), [
                (_("Net Result"), money(s.net, signed=True)),
                (_("Total Wagered"), money(s.total_wagered)),
                (_("Return per Bet"), _pct(s.net, s.total_wagered)),
                (_("Biggest Win"), money(s.biggest_win)),
                (_("Biggest Loss"), money(s.biggest_loss)),
                (_("Peak Bankroll"), money(s.peak_bankroll)),
                (_("Rebuys"), f"{s.rebuys:,}"),
            ]),
            self._group(_("Plays"), [
                (_("Blackjacks"), f"{s.blackjacks:,}"),
                (_("Busts"), f"{s.busts:,}"),
                (_("Doubles Won"), f"{s.doubles_won:,} / {s.doubles:,}"),
                (_("Splits"), f"{s.splits:,}"),
                (_("Surrenders"), f"{s.surrenders:,}"),
                (_("Insurance Won"), f"{s.insurance_won:,} / {s.insurance_taken:,}"),
                (_("Dealer Blackjacks"), f"{s.dealer_blackjacks:,}"),
                (_("Dealer Busts"), f"{s.dealer_busts:,} ({_pct(s.dealer_busts, s.rounds)})"),
            ]),
            self._group(_("Strategy"), [
                (_("Decisions"), f"{s.decisions:,}"),
                (_("Basic Strategy Accuracy"), _pct(s.correct_decisions, s.decisions)),
            ]),
        ]

    def _confirm_reset(self, *_args) -> None:
        dialog = Adw.AlertDialog(heading=_("Reset Statistics?"),
                                 body=_("All statistics will be permanently erased."))
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("reset", _("_Reset"))
        dialog.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_response)
        dialog.present(self)

    def _on_response(self, _dialog, response) -> None:
        if response != "reset":
            return
        self._on_reset()
        for group in self._groups:
            self.page.remove(group)
        self._fill(Stats())
