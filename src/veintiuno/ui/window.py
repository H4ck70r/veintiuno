# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window."""

from __future__ import annotations

from gettext import gettext as _

from gi.repository import Adw, Gio, GLib, Gtk, Pango

from .. import storage
from ..engine.game import BETTING, BLACKJACK, INSURANCE, PLAYER, ROUND_OVER, Game
from . import cardart
from .format import action_name, money
from .preferences import PreferencesDialog
from .sound import Sounds
from .stats import StatsDialog
from .table import TableView

CHIPS = (1, 5, 25, 100, 500, 1000)

PLAY_ACTIONS = ("hit", "stand", "double", "split", "surrender")


class ChipButton(Gtk.Button):
    def __init__(self, value: int):
        super().__init__()
        self.value = value
        self.add_css_class("flat")
        self.add_css_class("circular")
        self.add_css_class("chip-button")
        area = Gtk.DrawingArea(content_width=50, content_height=50)
        area.set_draw_func(lambda _a, cr, w, h: cardart.draw_chip(cr, w / 2, h / 2 - 1, w * 0.44, value))
        self.set_child(area)
        self.set_tooltip_text(_("Add a {amount} chip").format(amount=money(value)))
        self.update_property([Gtk.AccessibleProperty.LABEL], [_("Bet {amount}").format(amount=money(value))])


class Window(Adw.ApplicationWindow):
    def __init__(self, app, profile: storage.Profile):
        super().__init__(application=app, title="Veintiuno")
        self.set_default_size(1120, 780)
        self.set_size_request(360, 600)
        self.profile = profile
        self.game = Game(profile.rules, profile.bankroll, profile.stats)
        self.game.last_bet = profile.last_bet
        self._settling = False
        self.sounds = Sounds()

        self._build()
        self._install_actions()
        self._apply_prefs()
        self.table.set_game(self.game)
        self._refresh()
        if self.game.is_broke:
            self._show_page("broke")
        self.connect("close-request", self._on_close)

    # -- construction --------------------------------------------------

    def _build(self) -> None:
        self.title = Adw.WindowTitle(title="Veintiuno")
        header = Adw.HeaderBar()
        header.set_title_widget(self.title)

        hint = Gtk.Button(icon_name="dialog-information-symbolic", action_name="win.hint")
        hint.set_tooltip_text(_("Basic strategy hint (?)"))
        header.pack_start(hint)

        menu = Gio.Menu()
        section = Gio.Menu()
        section.append(_("_New Game"), "win.new-game")
        section.append(_("_Statistics"), "win.statistics")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(_("_Preferences"), "app.preferences")
        section.append(_("_Keyboard Shortcuts"), "win.show-help-overlay")
        section.append(_("_How to Play"), "win.how-to-play")
        section.append(_("_About Veintiuno"), "app.about")
        menu.append_section(None, section)
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, primary=True)
        menu_button.set_tooltip_text(_("Main Menu"))
        header.pack_end(menu_button)

        self.table = TableView()
        self.table.on_card_sound = lambda: self.sounds.play("card", 0.55)

        # Status line.
        self.bankroll_label = Gtk.Label(xalign=0)
        self.bankroll_label.add_css_class("heading")
        self.hint_label = Gtk.Label(ellipsize=Pango.EllipsizeMode.END)
        self.hint_label.add_css_class("dim-label")
        self.count_label = Gtk.Label(xalign=1)
        self.count_label.add_css_class("caption")
        self.count_label.add_css_class("numeric")
        status = Gtk.CenterBox(margin_start=12, margin_end=12, margin_top=6, margin_bottom=2)
        status.set_start_widget(self.bankroll_label)
        status.set_center_widget(self.hint_label)
        status.set_end_widget(self.count_label)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self._betting_page(), "betting")
        self.stack.add_named(self._insurance_page(), "insurance")
        self.stack.add_named(self._player_page(), "player")
        self.stack.add_named(self._round_over_page(), "round-over")
        self.stack.add_named(self._broke_page(), "broke")

        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bottom.add_css_class("table-controls")
        bottom.append(status)
        bottom.append(self.stack)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.table)
        content.append(bottom)

        self.toasts = Adw.ToastOverlay(child=content)
        view = Adw.ToolbarView(content=self.toasts)
        view.add_top_bar(header)
        self.set_content(view)

    def _row(self, *children, spacing=10):
        box = Gtk.Box(spacing=spacing, halign=Gtk.Align.CENTER)
        for child in children:
            box.append(child)
        return box

    def _page(self, *rows):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_top=8, margin_bottom=14, margin_start=12, margin_end=12)
        for row in rows:
            box.append(row)
        return box

    def _button(self, label, action, suggested=False, tooltip=None):
        button = Gtk.Button(label=label, action_name=action, use_underline=True)
        button.add_css_class("pill")
        if suggested:
            button.add_css_class("suggested-action")
        if tooltip:
            button.set_tooltip_text(tooltip)
        return button

    def _betting_page(self):
        self.chip_buttons = [ChipButton(v) for v in CHIPS]
        for i, button in enumerate(self.chip_buttons):
            button.set_action_name("win.chip")
            button.set_action_target_value(GLib.Variant("i", button.value))
            button.set_tooltip_text(_("Add {amount} ({key})").format(amount=money(button.value), key=i + 1))
        chips = self._row(*self.chip_buttons, spacing=4)
        actions = self._row(
            self._button(_("_Clear"), "win.clear", tooltip=_("Clear bet (Backspace)")),
            self._button(_("_Rebet"), "win.rebet", tooltip=_("Bet the same as last hand (B)")),
            self._button(_("_Deal"), "win.deal", suggested=True, tooltip=_("Deal (Enter)")),
        )
        return self._page(chips, actions)

    def _insurance_page(self):
        self.insurance_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.insurance_yes = self._button(_("_Take Insurance"), "win.insurance-yes", tooltip="Y")
        return self._page(self.insurance_label, self._row(
            self._button(_("_No Insurance"), "win.insurance-no", suggested=True, tooltip="N"),
            self.insurance_yes))

    def _player_page(self):
        buttons = [
            self._button(_("_Hit"), "win.hit", suggested=True, tooltip=_("Take another card (H)")),
            self._button(_("_Stand"), "win.stand", tooltip=_("Keep your hand (S)")),
            self._button(_("_Double"), "win.double", tooltip=_("Double the bet, take one card (D)")),
            self._button(_("S_plit"), "win.split", tooltip=_("Split the pair into two hands (P)")),
            self._button(_("Su_rrender"), "win.surrender", tooltip=_("Give up half the bet (R)")),
        ]
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           max_children_per_line=5, min_children_per_line=3,
                           column_spacing=8, row_spacing=8, halign=Gtk.Align.CENTER)
        for button in buttons:
            flow.append(button)
        for child in list(flow):
            child.set_focusable(False)
        return self._page(flow)

    def _round_over_page(self):
        self.summary_label = Gtk.Label()
        self.summary_label.add_css_class("title-3")
        return self._page(self.summary_label, self._row(
            self._button(_("_Change Bet"), "win.clear", tooltip=_("Place a new bet (Backspace)")),
            self._button(_("_Rebet and Deal"), "win.deal", suggested=True, tooltip=_("Same bet, next hand (Enter)")),
        ))

    def _broke_page(self):
        label = Gtk.Label(label=_("You're out of chips."))
        label.add_css_class("title-3")
        self.rebuy_button = self._button("", "win.rebuy", suggested=True)
        return self._page(label, self._row(self.rebuy_button))

    def _install_actions(self) -> None:
        def add(name, callback, param=None):
            action = Gio.SimpleAction.new(name, GLib.VariantType.new(param) if param else None)
            action.connect("activate", self._guard(callback))
            self.add_action(action)

        add("hit", lambda *_: self._play(self.game.hit))
        add("stand", lambda *_: self._play(self.game.stand))
        add("double", lambda *_: self._play(self.game.double))
        add("split", lambda *_: self._play(self.game.split))
        add("surrender", lambda *_: self._play(self.game.surrender))
        add("deal", self._on_deal)
        add("chip", self._on_chip, "i")
        add("clear", self._on_clear)
        add("rebet", self._on_rebet)
        add("insurance-yes", lambda *_: self._play(lambda: self.game.insurance(True)))
        add("insurance-no", lambda *_: self._play(lambda: self.game.insurance(False)))
        add("rebuy", self._on_rebuy)
        add("hint", self._on_hint)
        add("new-game", self._on_new_game)
        add("statistics", lambda *_: StatsDialog(self.game.stats, self._on_stats_reset).present(self))
        add("how-to-play", self._on_how_to_play)
        add("show-help-overlay", self._on_shortcuts)

        app = self.get_application()
        accels = {
            "win.hit": ["h"], "win.stand": ["s"], "win.double": ["d"], "win.split": ["p"],
            "win.surrender": ["r"], "win.deal": ["Return", "KP_Enter", "space"],
            "win.clear": ["BackSpace", "Delete"], "win.rebet": ["b"],
            "win.insurance-yes": ["y"], "win.insurance-no": ["n"],
            "win.hint": ["question", "F1"], "win.statistics": ["<Control>i"],
            "win.new-game": ["<Control>n"], "win.show-help-overlay": ["<Control>question"],
        }
        for action, keys in accels.items():
            app.set_accels_for_action(action, keys)
        for i, value in enumerate(CHIPS):
            app.set_accels_for_action(f"win.chip({value})", [str(i + 1), f"KP_{i + 1}"])

    def _guard(self, callback):
        """Ignore table shortcuts while a dialog covers the table."""
        def run(*args):
            if self.get_visible_dialog() is None:
                callback(*args)
        return run

    # -- state ---------------------------------------------------------

    def _enable(self, name: str, enabled: bool) -> None:
        self.lookup_action(name).set_enabled(enabled)

    def _show_page(self, name: str) -> None:
        self.stack.set_visible_child_name(name)

    def _refresh(self) -> None:
        game = self.game
        busy = self.table.cards_busy() or self._settling
        phase = game.phase

        for name in PLAY_ACTIONS:
            self._enable(name, False)
        for name in ("deal", "chip", "clear", "rebet", "insurance-yes",
                     "insurance-no", "rebuy"):
            self._enable(name, False)

        if phase == BETTING:
            if game.is_broke:
                self._show_page("broke")
                self.rebuy_button.set_label(_("Rebuy {amount}").format(
                    amount=money(self.profile.prefs.starting_bankroll)))
                self._enable("rebuy", True)
            else:
                self._show_page("betting")
                self._enable("deal", game.can_deal and not busy)
                self._enable("chip", True)
                self._enable("clear", game.bet > 0)
                self._enable("rebet", game.can_rebet() and game.bet != game.last_bet)
                for button in self.chip_buttons:
                    button.set_sensitive(game.bet + button.value <= game.max_bet)
        elif phase == INSURANCE:
            self._show_page("insurance")
            even_money = game.hands[0].is_blackjack
            self.insurance_label.set_label(
                _("The dealer shows an ace. You have blackjack: take even money?") if even_money else
                _("The dealer shows an ace. Insurance costs {amount}.").format(amount=money(game.insurance_cost)))
            self.insurance_yes.set_label(_("_Even Money") if even_money else _("_Take Insurance"))
            self._enable("insurance-yes", not busy)
            self._enable("insurance-no", not busy)
        elif phase == PLAYER:
            self._show_page("player")
            if not busy:
                self._enable("hit", game.can_hit())
                self._enable("stand", game.can_stand())
                self._enable("double", game.can_double())
                self._enable("split", game.can_split())
                self._enable("surrender", game.can_surrender())
        elif phase == ROUND_OVER:
            if not busy:
                self._show_page("round-over")
                self._enable("clear", True)
                self._enable("deal", True)

        self._enable("hint", phase == PLAYER and not busy)

        bankroll = money(game.bankroll)
        self.bankroll_label.set_label(_("Bankroll {amount}").format(amount=bankroll))
        self.title.set_subtitle(bankroll)

        if self.profile.prefs.show_count:
            pct = round(100 * game.shoe.remaining / game.shoe.size)
            self.count_label.set_label(_("RC {rc:+d} · TC {tc:+.1f} · Shoe {pct}%").format(
                rc=game.counter.running, tc=game.true_count(), pct=pct))
        else:
            self.count_label.set_label(_("Edge {edge:.2f}%").format(edge=game.rules.house_edge()))
            self.count_label.set_tooltip_text(_("House edge with perfect basic strategy"))

        if phase == PLAYER and not busy and self.profile.prefs.coach and len(game.hands) > 1:
            self.hint_label.set_label(_("Hand {n} of {total}").format(n=game.active + 1, total=len(game.hands)))
        elif phase == BETTING and not game.is_broke:
            self.hint_label.set_label(_("Bet {amount}").format(amount=money(game.bet)) if game.bet else
                                      _("Choose your chips"))
        elif phase != PLAYER:
            self.hint_label.set_label("")

    def _after_change(self) -> None:
        """Animate the latest game state, then refresh once the cards land."""
        self.table.sync()
        self._refresh()
        self.table.when_idle(self._on_cards_landed)

    def _on_cards_landed(self) -> None:
        game = self.game
        if game.phase == ROUND_OVER and not self._settling:
            self._settle_feedback()
        self._refresh()
        if game.phase == PLAYER and self.hint_label.get_label() == "" and self.profile.prefs.coach:
            self.hint_label.set_label(_("H Hit · S Stand · D Double · P Split · R Surrender"))

    def _settle_feedback(self) -> None:
        game = self.game
        net = game.round_net
        if any(h.result == BLACKJACK for h in game.hands):
            text, color, sound = _("Blackjack!"), (0.98, 0.82, 0.3), "blackjack"
        elif net > 0:
            text, color, sound = money(net, signed=True), (0.5, 0.95, 0.6), "win"
        elif net < 0:
            text, color, sound = money(net, signed=True), (1.0, 0.55, 0.55), "lose"
        else:
            text, color, sound = _("Push"), (0.9, 0.9, 0.9), "push"
        self.sounds.play(sound, 0.5)
        if game.dealer.busted:
            self.summary_label.set_label(_("Dealer busts · {net}").format(net=money(net, signed=True)))
        else:
            self.summary_label.set_label(_("Dealer {total} · {net}").format(
                total=game.dealer.total, net=money(net, signed=True)))
        if game.insurance_result:
            self._toast(_("Insurance won") if game.insurance_result == "win" else _("Insurance lost"))
        self.table.banner(text, color)
        self._save()

    def _toast(self, text: str, timeout: int = 2) -> None:
        toast = Adw.Toast(title=text, timeout=timeout)
        self.toasts.add_toast(toast)

    # -- handlers ------------------------------------------------------

    def _play(self, step) -> None:
        if self.table.cards_busy():
            return
        if step in (self.game.double, self.game.split):
            self.sounds.play("chip")
        before = self.game.stats.decisions
        step()
        mistake = self.game.last_mistake
        if (self.profile.prefs.coach and mistake and mistake.advice
                and self.game.stats.decisions > before):
            self._toast(_("Basic strategy: {advice} (you chose {action})").format(
                advice=action_name(mistake.advice), action=action_name(mistake.action)), 3)
        self.hint_label.set_label("")
        self._after_change()

    def _on_deal(self, *_args) -> None:
        game = self.game
        if self.table.cards_busy():
            return
        if game.phase == ROUND_OVER:
            game.new_round()
            if not game.rebet():
                self._after_change()
                return
        if not game.deal():
            return
        if game.just_shuffled:
            game.just_shuffled = False
            self.table.discarded = 0
            self.sounds.play("shuffle", 0.6)
            self._toast(_("New shoe: {decks} decks shuffled").format(decks=game.rules.decks)
                        if game.rules.decks > 1 else _("New deck shuffled"))
        self._after_change()

    def _on_chip(self, _action, value) -> None:
        if self.game.phase == ROUND_OVER and not self.table.cards_busy():
            self.game.new_round()
            self.table.sync()
        if self.game.add_chip(value.get_int32()):
            self.sounds.play("chip")
            self.table.queue_draw()
        self._refresh()

    def _on_clear(self, *_args) -> None:
        if self.game.phase == ROUND_OVER:
            if not self.table.cards_busy():
                self.game.new_round()
                self._after_change()
            return
        self.game.clear_bet()
        self.table.queue_draw()
        self._refresh()

    def _on_rebet(self, *_args) -> None:
        if self.game.rebet():
            self.sounds.play("chip")
        self.table.queue_draw()
        self._refresh()

    def _on_rebuy(self, *_args) -> None:
        self.game.rebuy(self.profile.prefs.starting_bankroll)
        self._toast(_("Rebought {amount}").format(amount=money(self.profile.prefs.starting_bankroll)))
        self._save()
        self._refresh()

    def _on_hint(self, *_args) -> None:
        advice = self.game.advice()
        if advice:
            self.hint_label.set_label(_("Basic strategy says: {action}").format(action=action_name(advice)))

    def _on_new_game(self, *_args) -> None:
        dialog = Adw.AlertDialog(
            heading=_("Start a New Game?"),
            body=_("Your bankroll goes back to {amount} and a fresh shoe is shuffled. "
                   "Statistics are kept.").format(amount=money(self.profile.prefs.starting_bankroll)))
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("new", _("_New Game"))
        dialog.set_response_appearance("new", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("new")
        dialog.connect("response", self._on_new_game_response)
        dialog.present(self)

    def _on_new_game_response(self, _dialog, response) -> None:
        if response != "new":
            return
        self.game = Game(self.game.rules, self.profile.prefs.starting_bankroll, self.game.stats)
        self.table.discarded = 0
        self.table.set_game(self.game)
        self._save()
        self._refresh()

    def _on_stats_reset(self) -> None:
        from ..engine.game import Stats
        self.game.stats = Stats(peak_bankroll=self.game.bankroll)
        self._save()

    def _on_how_to_play(self, *_args) -> None:
        from .help import HelpDialog
        HelpDialog().present(self)

    def _on_shortcuts(self, *_args) -> None:
        from .help import ShortcutsDialog
        ShortcutsDialog().present(self)

    # -- preferences ---------------------------------------------------

    def show_preferences(self) -> None:
        dialog = PreferencesDialog(self.game.rules, self.profile.prefs, self._on_prefs_changed)
        dialog.present(self)

    def _on_prefs_changed(self, rules, prefs) -> None:
        mid_round = self.game.phase not in (BETTING,)
        if rules != self.game.rules:
            self.game.set_rules(rules)
            if mid_round:
                self._toast(_("New rules apply from the next hand"))
        self.profile.prefs = prefs
        self._apply_prefs()
        self.table.queue_draw()
        self._refresh()
        self._save()

    def _apply_prefs(self) -> None:
        prefs = self.profile.prefs
        self.table.speed = storage.ANIMATION_SPEEDS[prefs.animation_speed]
        self.table.back = prefs.card_back
        self.table.show_totals = prefs.show_totals
        self.sounds.enabled = prefs.sound

    # -- persistence ---------------------------------------------------

    def _save(self) -> None:
        game = self.game
        self.profile.bankroll = round(game.bankroll + game.money_on_table, 2)
        self.profile.last_bet = game.last_bet
        self.profile.rules = game._pending_rules or game.rules
        self.profile.stats = game.stats
        try:
            storage.save(self.profile)
        except OSError as err:
            self._toast(_("Could not save your progress: {error}").format(error=err.strerror))

    def _on_close(self, *_args) -> bool:
        self._save()
        return False
