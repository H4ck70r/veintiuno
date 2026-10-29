# SPDX-License-Identifier: GPL-3.0-or-later
"""Preferences: table rules and game options."""

from __future__ import annotations

from dataclasses import replace
from gettext import gettext as _

from gi.repository import Adw, Gtk

from ..engine.rules import DOUBLE_10_11, DOUBLE_9_11, DOUBLE_ANY, Rules
from ..storage import Preferences


def _combo(title, subtitle, options, current):
    """options: list of (value, label)."""
    row = Adw.ComboRow(title=title, subtitle=subtitle or "")
    row.set_model(Gtk.StringList.new([label for _value, label in options]))
    values = [value for value, _label in options]
    row.set_selected(values.index(current) if current in values else 0)
    row.values = values
    return row


def _spin(title, subtitle, lower, upper, step, value):
    row = Adw.SpinRow.new_with_range(lower, upper, step)
    row.set_title(title)
    if subtitle:
        row.set_subtitle(subtitle)
    row.set_value(value)
    return row


def _switch(title, subtitle, active):
    row = Adw.SwitchRow(title=title, subtitle=subtitle or "")
    row.set_active(active)
    return row


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, rules: Rules, prefs: Preferences, on_changed):
        super().__init__()
        self.set_search_enabled(True)
        self._rules = rules
        self._prefs = prefs
        self._on_changed = on_changed
        self._loading = True

        # Game page.
        game_page = Adw.PreferencesPage(title=_("Game"), icon_name="applications-games-symbolic")
        look = Adw.PreferencesGroup(title=_("Table"))
        self.speed = _combo(_("Animation Speed"), None, [
            ("off", _("Off")), ("fast", _("Fast")), ("normal", _("Normal")), ("slow", _("Slow"))],
            prefs.animation_speed)
        self.back = _combo(_("Card Back"), None, [
            ("red", _("Red")), ("blue", _("Blue")), ("green", _("Green"))], prefs.card_back)
        self.totals = _switch(_("Show Hand Totals"), None, prefs.show_totals)
        self.sound = _switch(_("Sound Effects"), None, prefs.sound)
        for row in (self.speed, self.back, self.totals, self.sound):
            look.add(row)
        game_page.add(look)

        training = Adw.PreferencesGroup(title=_("Training"))
        self.coach = _switch(_("Strategy Coach"),
                             _("Warn when a decision differs from basic strategy"), prefs.coach)
        self.count = _switch(_("Show Card Count"),
                             _("Display the Hi-Lo running and true count"), prefs.show_count)
        training.add(self.coach)
        training.add(self.count)
        game_page.add(training)

        money_group = Adw.PreferencesGroup(title=_("Money"))
        self.bankroll = _spin(_("Starting Bankroll"), _("Used for new games and rebuys"),
                              100, 1_000_000, 100, prefs.starting_bankroll)
        self.min_bet = _spin(_("Minimum Bet"), None, 1, 10_000, 1, rules.min_bet)
        self.max_bet = _spin(_("Maximum Bet"), None, 5, 1_000_000, 5, rules.max_bet)
        for row in (self.bankroll, self.min_bet, self.max_bet):
            money_group.add(row)
        game_page.add(money_group)
        self.add(game_page)

        # Rules page.
        rules_page = Adw.PreferencesPage(title=_("Rules"), icon_name="view-list-symbolic", name="rules")
        shoe = Adw.PreferencesGroup(title=_("Shoe and Dealer"))
        self.edge_label = Gtk.Label(css_classes=["dim-label", "numeric"])
        shoe.set_header_suffix(self.edge_label)
        self.decks = _spin(_("Decks"), None, 1, 8, 1, rules.decks)
        self.penetration = _spin(_("Penetration"), _("Percent of the shoe dealt before reshuffling"),
                                 50, 90, 5, round(rules.penetration * 100))
        self.h17 = _switch(_("Dealer Hits Soft 17"), None, rules.dealer_hits_soft17)
        self.peek = _switch(_("Dealer Peeks for Blackjack"),
                            _("Off plays the European no-hole-card game: "
                              "doubles and splits are lost to a dealer blackjack"),
                            rules.dealer_peek)
        self.payout = _combo(_("Blackjack Pays"), None, [("3:2", "3:2"), ("6:5", "6:5")],
                             rules.blackjack_pays)
        for row in (self.decks, self.penetration, self.h17, self.peek, self.payout):
            shoe.add(row)
        rules_page.add(shoe)

        player = Adw.PreferencesGroup(title=_("Player Options"))
        self.double_on = _combo(_("Double Down On"), None, [
            (DOUBLE_ANY, _("Any two cards")), (DOUBLE_9_11, _("9, 10 or 11")),
            (DOUBLE_10_11, _("10 or 11"))], rules.double_on)
        self.das = _switch(_("Double After Split"), None, rules.double_after_split)
        self.max_hands = _spin(_("Maximum Hands After Splitting"), None, 2, 4, 1, rules.max_hands)
        self.resplit_aces = _switch(_("Resplit Aces"), None, rules.resplit_aces)
        self.hit_aces = _switch(_("Hit Split Aces"), None, rules.hit_split_aces)
        self.unlike_tens = _switch(_("Split Unlike Tens"), _("For example, a king and a queen"),
                                   rules.split_unlike_tens)
        self.surrender = _switch(_("Late Surrender"), None, rules.late_surrender)
        self.insurance = _switch(_("Insurance"), None, rules.insurance)
        for row in (self.double_on, self.das, self.max_hands, self.resplit_aces, self.hit_aces,
                    self.unlike_tens, self.surrender, self.insurance):
            player.add(row)
        rules_page.add(player)

        presets = Adw.PreferencesGroup(title=_("Presets"))
        for title, subtitle, preset in (
            (_("Las Vegas Strip"), _("6 decks, S17, DAS, late surrender, 3:2"), Rules()),
            (_("Atlantic City"), _("8 decks, S17, DAS, late surrender, 3:2"),
             Rules(decks=8)),
            (_("Downtown Single Deck"), _("1 deck, H17, doubles on 10–11 only, 3:2"),
             Rules(decks=1, dealer_hits_soft17=True, double_on=DOUBLE_10_11,
                   double_after_split=False, late_surrender=False, max_hands=2)),
            (_("European"), _("6 decks, no hole card, doubles on 9–11, no surrender"),
             Rules(dealer_peek=False, double_on=DOUBLE_9_11, late_surrender=False,
                   max_hands=3)),
        ):
            row = Adw.ActionRow(title=title, subtitle=subtitle, activatable=True)
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", self._on_preset, preset)
            presets.add(row)
        rules_page.add(presets)
        self.add(rules_page)

        for row in (self.speed, self.back, self.payout, self.double_on):
            row.connect("notify::selected", self._changed)
        for row in (self.totals, self.sound, self.coach, self.count, self.h17, self.peek, self.das,
                    self.resplit_aces, self.hit_aces, self.unlike_tens, self.surrender,
                    self.insurance):
            row.connect("notify::active", self._changed)
        for row in (self.bankroll, self.min_bet, self.max_bet, self.decks, self.penetration,
                    self.max_hands):
            row.connect("notify::value", self._changed)
        self._loading = False
        self._update_edge(rules)

    def _value(self, combo):
        return combo.values[combo.get_selected()]

    def _collect(self):
        min_bet = int(self.min_bet.get_value())
        max_bet = max(int(self.max_bet.get_value()), min_bet)
        rules = Rules.from_dict(dict(
            self._rules.to_dict(),
            decks=int(self.decks.get_value()),
            penetration=self.penetration.get_value() / 100,
            dealer_hits_soft17=self.h17.get_active(),
            dealer_peek=self.peek.get_active(),
            blackjack_pays=self._value(self.payout),
            double_on=self._value(self.double_on),
            double_after_split=self.das.get_active(),
            max_hands=int(self.max_hands.get_value()),
            resplit_aces=self.resplit_aces.get_active(),
            hit_split_aces=self.hit_aces.get_active(),
            split_unlike_tens=self.unlike_tens.get_active(),
            late_surrender=self.surrender.get_active(),
            insurance=self.insurance.get_active(),
            min_bet=min_bet,
            max_bet=max_bet,
        ))
        prefs = replace(
            self._prefs,
            animation_speed=self._value(self.speed),
            card_back=self._value(self.back),
            show_totals=self.totals.get_active(),
            sound=self.sound.get_active(),
            coach=self.coach.get_active(),
            show_count=self.count.get_active(),
            starting_bankroll=int(self.bankroll.get_value()),
        )
        return rules, prefs

    def _changed(self, *_args):
        if self._loading:
            return
        rules, prefs = self._collect()
        self._rules, self._prefs = rules, prefs
        self._update_edge(rules)
        self._on_changed(rules, prefs)

    def _update_edge(self, rules: Rules):
        self.edge_label.set_label(_("House edge ≈ {edge:.2f}%").format(edge=rules.house_edge()))

    def _on_preset(self, _row, preset: Rules):
        self._loading = True
        self.decks.set_value(preset.decks)
        self.penetration.set_value(round(preset.penetration * 100))
        self.h17.set_active(preset.dealer_hits_soft17)
        self.peek.set_active(preset.dealer_peek)
        self.payout.set_selected(self.payout.values.index(preset.blackjack_pays))
        self.double_on.set_selected(self.double_on.values.index(preset.double_on))
        self.das.set_active(preset.double_after_split)
        self.max_hands.set_value(preset.max_hands)
        self.resplit_aces.set_active(preset.resplit_aces)
        self.hit_aces.set_active(preset.hit_split_aces)
        self.unlike_tens.set_active(preset.split_unlike_tens)
        self.surrender.set_active(preset.late_surrender)
        self.insurance.set_active(preset.insurance)
        self._loading = False
        self._changed()
        self.add_toast(Adw.Toast(title=_("Preset applied"), timeout=2))
