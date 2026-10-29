# SPDX-License-Identifier: GPL-3.0-or-later
"""The felt: draws and animates the cards on the table."""

from __future__ import annotations

import math
from dataclasses import dataclass
from gettext import gettext as _

import cairo
from gi.repository import GLib, Gtk

from ..engine.cards import Card, hand_total
from ..engine.game import BETTING, BLACKJACK, INSURANCE, PUSH, ROUND_OVER, SURRENDERED, WIN, Game
from . import cardart
from .format import money, result_name

CARD_RATIO = 0.714
GOLD = (0.95, 0.80, 0.42)


def _now() -> float:
    return GLib.get_monotonic_time() / 1e6


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


@dataclass
class Sprite:
    card: Card
    x: float
    y: float
    sx: float = 0
    sy: float = 0
    tx: float = 0
    ty: float = 0
    move_start: float = 0
    move_dur: float = 0
    shown_up: bool = False      # face the card currently shows once flips finish
    flip_start: float = 0
    flip_dur: float = 0
    flip_from_up: bool = False
    leaving: bool = False
    z: int = 0

    def end_time(self) -> float:
        return max(self.move_start + self.move_dur, self.flip_start + self.flip_dur)

    def position(self, now: float) -> tuple[float, float]:
        if self.move_dur <= 0 or now >= self.move_start + self.move_dur:
            return self.tx, self.ty
        if now <= self.move_start:
            return self.sx, self.sy
        t = _ease((now - self.move_start) / self.move_dur)
        return self.sx + (self.tx - self.sx) * t, self.sy + (self.ty - self.sy) * t

    def face(self, now: float) -> tuple[bool, float]:
        """Return (face_up, horizontal scale) at time `now`."""
        if self.flip_dur <= 0 or now >= self.flip_start + self.flip_dur:
            return self.shown_up, 1.0
        if now <= self.flip_start:
            return self.flip_from_up, 1.0
        p = (now - self.flip_start) / self.flip_dur
        up = self.flip_from_up if p < 0.5 else self.shown_up
        return up, abs(math.cos(math.pi * p))

    def arrived(self, now: float) -> bool:
        return now >= self.end_time()


class TableView(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_draw_func(self._draw)
        self.game: Game | None = None
        self.speed = 1.0
        self.back = "red"
        self.show_totals = True
        self.sprites: dict[int, Sprite] = {}
        self.discarded = 0
        self._queue_end = 0.0
        self._tick_id = 0
        self._idle_callbacks = []
        self._z = 0
        self._banner: tuple[str, float, tuple] | None = None
        self._last_size = (0, 0)
        self.on_card_sound = None  # called when a card lands or flips
        self._flying: list[tuple[int, float, float]] = []  # chips tossed onto the bet spot

    # -- public API ----------------------------------------------------

    def set_game(self, game: Game) -> None:
        self.game = game
        self.sprites.clear()
        self.sync(animate=False)

    def toss_chip(self, value: int) -> None:
        """Animate a chip flying from the rack onto the bet spot."""
        if self.speed > 0:
            self._flying.append((value, _now(), 0.34 * max(self.speed, 0.6)))
            self._ensure_tick()
        self.queue_draw()

    def is_animating(self) -> bool:
        now = _now()
        if any(not s.arrived(now) for s in self.sprites.values()):
            return True
        if any(now < start + dur for _v, start, dur in self._flying):
            return True
        return self._banner is not None and now < self._banner[1]

    def cards_busy(self) -> bool:
        now = _now()
        return any(not s.arrived(now) for s in self.sprites.values())

    def when_idle(self, callback) -> None:
        """Run callback once every card has finished moving."""
        if not self.cards_busy():
            callback()
        else:
            self._idle_callbacks.append(callback)

    def banner(self, text: str, rgb=GOLD, seconds: float = 1.4) -> None:
        self._banner = (text, _now() + max(seconds * max(self.speed, 0.6), 0.8), rgb)
        self._ensure_tick()

    def card_visible(self, card: Card) -> bool:
        """Whether the card has landed face up (used for running totals)."""
        sprite = self.sprites.get(card.id)
        if sprite is None:
            return False
        now = _now()
        up, _scale = sprite.face(now)
        return up and sprite.arrived(now)

    # -- layout --------------------------------------------------------

    def _metrics(self):
        w, h = self.get_width(), self.get_height()
        card_w = max(36.0, min(w * 0.2, h / 5.0, 190.0))
        return w, h, card_w, card_w / CARD_RATIO

    def _rows(self):
        """Vertical positions: (dealer cards top, player cards top)."""
        w, h, cw, ch = self._metrics()
        dealer_y = cw * 0.22
        player_y = max(h - ch - cw * 0.95, dealer_y + ch + cw * 1.05)
        return dealer_y, player_y

    def _shoe_pos(self):
        w, h, cw, ch = self._metrics()
        return w - cw * 1.45, h * 0.04

    def _discard_pos(self):
        w, h, cw, ch = self._metrics()
        return cw * 0.45, h * 0.04

    def _hand_slots(self, count: int):
        w, h, cw, ch = self._metrics()
        slot_w = cw * 2.1
        gap = cw * 0.35
        total = count * slot_w + (count - 1) * gap
        if total > w * 0.96:
            scale = w * 0.96 / total
            slot_w *= scale
            gap *= scale
            total = w * 0.96
        x0 = (w - total) / 2
        return [(x0 + i * (slot_w + gap), slot_w) for i in range(count)]

    def _targets(self) -> dict[int, tuple[float, float]]:
        game = self.game
        targets = {}
        if game is None:
            return targets
        w, h, cw, ch = self._metrics()

        dealer_y, base_y = self._rows()
        dealer = game.dealer.cards
        if dealer:
            step = cw * 0.62
            x0 = w / 2 - (cw + step * max(len(dealer), 2) - step) / 2
            for i, card in enumerate(dealer):
                targets[card.id] = (x0 + i * step, dealer_y)

        slots = self._hand_slots(len(game.hands)) if game.hands else []
        for hand, (sx, slot_w) in zip(game.hands, slots):
            n = len(hand.cards)
            step = cw * 0.3
            if n > 1 and cw + step * (n - 1) > slot_w:
                step = (slot_w - cw) / (n - 1)
            for i, card in enumerate(hand.cards):
                dy = -ch * 0.035 * i
                if hand.doubled and i == 2:
                    dy -= ch * 0.04
                targets[card.id] = (sx + (slot_w - cw - step * 2) / 2 + i * step, base_y + dy)
        return targets

    # -- syncing -------------------------------------------------------

    def relayout(self) -> None:
        """Snap every card to its place (after a resize)."""
        targets = self._targets()
        for cid, sprite in self.sprites.items():
            if cid in targets:
                sprite.sx, sprite.sy = sprite.tx, sprite.ty = targets[cid]

    def sync(self, animate: bool = True) -> None:
        game = self.game
        if game is None:
            return
        animate = animate and self.speed > 0 and self.get_width() > 0
        now = _now()
        targets = self._targets()
        dur = 0.32 * self.speed
        delay = 0.24 * self.speed
        flip = 0.26 * self.speed

        # Cards that left the table go to the discard tray.
        dx, dy = self._discard_pos()
        for cid, sprite in list(self.sprites.items()):
            if cid in targets:
                continue
            if not animate:
                del self.sprites[cid]
                self.discarded += 1
                continue
            if not sprite.leaving:
                sprite.leaving = True
                sprite.sx, sprite.sy = sprite.position(now)
                sprite.tx, sprite.ty = dx, dy
                sprite.move_start, sprite.move_dur = now, dur
                if sprite.shown_up:
                    sprite.flip_from_up, sprite.shown_up = True, False
                    sprite.flip_start, sprite.flip_dur = now, dur
            elif sprite.arrived(now):
                del self.sprites[cid]
                self.discarded += 1

        # Order new cards and reveals the way they were dealt.
        events = []
        cards = {c.id: c for c in game.dealer.cards}
        for hand in game.hands:
            cards.update({c.id: c for c in hand.cards})
        for cid, card in cards.items():
            sprite = self.sprites.get(cid)
            if sprite is None:
                events.append((game.seq_of.get(cid, 0), "deal", card))
            elif sprite.shown_up != card.face_up:
                events.append((game.reveal_seq if card.face_up else 0, "flip", card))
        events.sort(key=lambda e: e[0])

        sx, sy = self._shoe_pos()
        start = max(now, self._queue_end)
        for _seq, kind, card in events:
            tx, ty = targets[card.id]
            if kind == "deal":
                self._z += 1
                sprite = Sprite(card, sx, sy, sx, sy, tx, ty, z=self._z)
                sprite.shown_up = card.face_up
                if animate:
                    sprite.move_start, sprite.move_dur = start, dur
                    if card.face_up:
                        sprite.flip_from_up = False
                        sprite.flip_start, sprite.flip_dur = start + dur * 0.45, dur * 0.55
                self.sprites[card.id] = sprite
            else:
                sprite = self.sprites[card.id]
                sprite.flip_from_up = sprite.shown_up
                sprite.shown_up = card.face_up
                if animate:
                    sprite.flip_start, sprite.flip_dur = start, flip
            if animate:
                self._schedule_sound(start - now)
                start += delay
        if events and animate:
            self._queue_end = start

        # Existing cards slide to their (possibly new) spots, e.g. after a split.
        for cid, (tx, ty) in targets.items():
            sprite = self.sprites[cid]
            if (sprite.tx, sprite.ty) != (tx, ty):
                sprite.sx, sprite.sy = sprite.position(now)
                sprite.tx, sprite.ty = tx, ty
                sprite.move_start, sprite.move_dur = (now, dur) if animate else (0, 0)

        if animate:
            self._ensure_tick()
        else:
            self._fire_idle()
        self.queue_draw()

    def _schedule_sound(self, seconds: float) -> None:
        if self.on_card_sound is None:
            return
        def play():
            self.on_card_sound()
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(max(0, int(seconds * 1000)), play)

    def _ensure_tick(self) -> None:
        if not self._tick_id:
            self._tick_id = self.add_tick_callback(self._on_tick)

    def _on_tick(self, _widget, _clock):
        now = _now()
        self._flying = [f for f in self._flying if now < f[1] + f[2]]
        for cid, sprite in list(self.sprites.items()):
            if sprite.leaving and sprite.arrived(now):
                del self.sprites[cid]
                self.discarded += 1
        self.queue_draw()
        if not self.cards_busy():
            self._fire_idle()
        if self.is_animating():
            return GLib.SOURCE_CONTINUE
        self._banner = None
        self._tick_id = 0
        return GLib.SOURCE_REMOVE

    def _fire_idle(self) -> None:
        callbacks, self._idle_callbacks = self._idle_callbacks, []
        for callback in callbacks:
            callback()

    # -- drawing -------------------------------------------------------

    def _draw(self, _area, cr, width, height):
        if (width, height) != self._last_size:
            self._last_size = (width, height)
            self.relayout()
        now = _now()
        w, h, cw, ch = self._metrics()
        self._draw_felt(cr, w, h, cw)
        self._draw_shoe(cr, cw, ch)

        game = self.game
        if game is None:
            return
        busy = self.cards_busy()
        dealer_y, player_y = self._rows()
        badge_y = player_y + ch + cw * 0.08
        chips_y = badge_y + cw * 0.62

        # Bets and chips.
        if game.phase == BETTING:
            self._flying = [f for f in self._flying if now < f[1] + f[2]]
            in_air = sum(v for v, _s, _d in self._flying)
            spot_y = player_y + ch * 0.45
            self._draw_bet_spot(cr, w / 2, spot_y, cw, max(0, game.bet - in_air), game.bet)
            for value, start, dur in self._flying:
                t = _ease((now - start) / dur) if now > start else 0
                fx = w / 2 + (1 - t) * cw * 0.6
                fy = h + cw * 0.3 + (spot_y + cw * 0.08 - h - cw * 0.3) * t - math.sin(math.pi * t) * cw * 0.6
                cardart.draw_chip(cr, fx, fy, cw * 0.28 * (1.25 - 0.25 * t), value)
        else:
            slots = self._hand_slots(len(game.hands)) if game.hands else []
            for i, (hand, (sx, slot_w)) in enumerate(zip(game.hands, slots)):
                self._draw_stack(cr, sx + slot_w / 2, chips_y, cw * 0.2, hand.bet)
            if game.insurance_bet:
                ix = w / 2 + cw * 2.4
                self._draw_stack(cr, ix, dealer_y + ch * 0.55, cw * 0.17, game.insurance_bet)
                cardart.draw_text(cr, _("Insurance"), ix, dealer_y + ch * 0.55 + cw * 0.25,
                                  cw * 0.12, GOLD, weight="Bold")

        # Cards, back to front.
        active = game.current_hand
        active_ids = {c.id for c in active.cards} if active and len(game.hands) > 1 else set()
        for sprite in sorted(self.sprites.values(), key=lambda s: (s.leaving, s.z)):
            x, y = sprite.position(now)
            up, scale = sprite.face(now)
            alpha = 1.0
            if sprite.leaving and sprite.move_dur:
                alpha = 1 - _ease((now - sprite.move_start) / sprite.move_dur) * 0.8
            cardart.draw_card(cr, sprite.card, x, y, cw, ch, up, self.back, scale, alpha,
                              highlight=sprite.card.id in active_ids,
                              scale=self.get_scale_factor())

        # Totals and results.
        if game.dealer.cards and self.show_totals:
            visible = [c for c in game.dealer.cards if self.card_visible(c)]
            if visible:
                total = hand_total(visible)[0]
                label = _("Blackjack") if game.dealer.is_blackjack and len(visible) == 2 else str(total)
                n = max(len(game.dealer.cards), 2)
                right = w / 2 + (cw + cw * 0.62 * (n - 1)) / 2
                bx, by = right + cw * 0.45, dealer_y + ch * 0.4
                if bx + cw * 0.4 > self._shoe_pos()[0] - cw * 0.15:
                    # Not enough room beside the cards (narrow window): put it underneath.
                    bx, by = w / 2, dealer_y + ch + cw * 0.04
                self._draw_badge(cr, label, bx, by, cw)

        slots = self._hand_slots(len(game.hands)) if game.hands else []
        settled = game.phase == ROUND_OVER and not busy
        for hand, (sx, slot_w) in zip(game.hands, slots):
            cx = sx + slot_w / 2
            visible = [c for c in hand.cards if self.card_visible(c)]
            if self.show_totals and visible:
                total, soft = hand_total(visible)
                label = f"{total - 10}/{total}" if soft and total < 21 else str(total)
                if hand.is_blackjack and len(visible) == 2:
                    label = "21"
                self._draw_badge(cr, label, cx, badge_y, cw,
                                 active=hand is active and len(game.hands) > 1)
            if settled and hand.result:
                self._draw_result(cr, hand, cx, player_y + ch * 0.5, cw)

        if game.phase == INSURANCE and not busy:
            n = max(len(game.dealer.cards), 2)
            left = w / 2 - (cw + cw * 0.62 * (n - 1)) / 2
            tw, _th = cardart.text_size(cr, _("Insurance?"), cw * 0.16)
            bx = left - cw * 0.3 - tw / 2
            if bx - tw / 2 < self._discard_pos()[0] + cw * 1.3:
                self._draw_badge(cr, _("Insurance?"), w / 2, dealer_y + ch + cw * 0.3, cw)
            else:
                self._draw_badge(cr, _("Insurance?"), bx, dealer_y + ch * 0.4, cw)

        if self._banner and now < self._banner[1]:
            text, end, rgb = self._banner
            alpha = min(1.0, (end - now) / 0.4)
            self._draw_banner(cr, text, w / 2, (dealer_y + ch + player_y) / 2, cw, rgb, alpha)

    def _draw_felt(self, cr, w, h, cw):
        grad = cairo.RadialGradient(w / 2, h * 0.35, 0, w / 2, h * 0.35, max(w, h) * 0.8)
        grad.add_color_stop_rgb(0, 0.10, 0.45, 0.27)
        grad.add_color_stop_rgb(0.65, 0.05, 0.32, 0.18)
        grad.add_color_stop_rgb(1, 0.02, 0.18, 0.10)
        cr.set_source(grad)
        cr.paint()

        # Table arc and printed rules.
        game = self.game
        dealer_y, player_y = self._rows()
        ch = cw / CARD_RATIO
        arc_bottom = dealer_y + ch + cw * 0.22
        radius = w * 1.2
        cr.save()
        cr.set_source_rgba(*GOLD, 0.35)
        cr.set_line_width(max(1.5, cw * 0.02))
        half = math.asin(min(1.0, (w / 2 - cw * 1.9) / radius))
        cr.arc(w / 2, arc_bottom - radius, radius, math.pi / 2 - half, math.pi / 2 + half)
        cr.stroke()
        cr.restore()
        if game is None or w < cw * 5.5:
            return  # narrow windows need the space for badges
        rules = game.rules
        lines = [
            _("BLACKJACK PAYS {num} TO {den}").format(num=rules.blackjack_pays.split(":")[0],
                                                     den=rules.blackjack_pays.split(":")[1]),
            _("Dealer hits soft 17") if rules.dealer_hits_soft17 else _("Dealer stands on all 17s"),
        ]
        if rules.insurance:
            lines.append(_("Insurance pays 2 to 1"))
        y = arc_bottom + cw * 0.06
        for i, line in enumerate(lines):
            px = cw * (0.135 if i == 0 else 0.085)
            hgt = cardart.draw_text(cr, line, w / 2, y, px, (0.95, 0.85, 0.55),
                                    weight="Bold" if i == 0 else "Regular")
            y += hgt * 1.05
        limits = _("Table limits {min} – {max}").format(min=money(rules.min_bet), max=money(rules.max_bet))
        cardart.draw_text(cr, limits, w / 2, y + cw * 0.02, cw * 0.085, (0.85, 0.85, 0.75),
                          weight="Regular")

    def _draw_shoe(self, cr, cw, ch):
        game = self.game
        sx, sy = self._shoe_pos()
        # Shoe box.
        cardart.rounded_rect(cr, sx - cw * 0.12, sy - cw * 0.08, cw * 1.3, ch * 1.12, cw * 0.1)
        cr.set_source_rgba(0, 0, 0, 0.3)
        cr.fill()
        if game is not None:
            layers = max(1, min(6, round(6 * game.shoe.remaining / game.shoe.size)))
            for i in range(layers):
                cardart.draw_card(cr, None, sx + i * 1.2, sy - i * 1.2, cw, ch, False, self.back,
                                  scale=self.get_scale_factor())
        # Discard tray.
        dx, dy = self._discard_pos()
        cardart.rounded_rect(cr, dx - cw * 0.12, dy - cw * 0.08, cw * 1.3, ch * 1.12, cw * 0.1)
        cr.set_source_rgba(0, 0, 0, 0.3)
        cr.fill()
        if self.discarded and game is not None:
            layers = max(1, min(6, round(6 * self.discarded / game.shoe.size) + 1))
            for i in range(layers):
                cardart.draw_card(cr, None, dx + i * 1.2, dy - i * 1.2, cw, ch, False, self.back,
                                  scale=self.get_scale_factor())

    def _draw_bet_spot(self, cr, cx, cy, cw, bet, label_amount=None):
        r = cw * 0.55
        cr.save()
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source_rgba(*GOLD, 0.65)
        cr.set_line_width(max(1.5, cw * 0.025))
        cr.set_dash([cw * 0.06, cw * 0.04])
        cr.stroke()
        cr.restore()
        label_amount = bet if label_amount is None else label_amount
        if bet:
            self._draw_stack(cr, cx, cy + cw * 0.08, cw * 0.28, bet)
        if label_amount:
            cardart.draw_text(cr, money(label_amount), cx, cy + r + cw * 0.1, cw * 0.2, (1, 1, 1))
        else:
            cardart.draw_text(cr, _("Place your bet"), cx, cy - cw * 0.08, cw * 0.13, GOLD)

    def _draw_stack(self, cr, cx, cy, radius, amount):
        chips = cardart.chips_for(amount)
        for i, value in enumerate(reversed(chips)):
            cardart.draw_chip(cr, cx, cy - i * radius * 0.22, radius, value,
                              label=i == len(chips) - 1)

    def _draw_badge(self, cr, text, cx, top, cw, active=False):
        px = cw * 0.16
        tw, th = cardart.text_size(cr, text, px)
        pad = px * 0.5
        bw, bh = tw + pad * 2, th + pad * 0.6
        cardart.rounded_rect(cr, cx - bw / 2, top, bw, bh, bh / 2)
        if active:
            cr.set_source_rgba(0.95, 0.75, 0.2, 0.95)
        else:
            cr.set_source_rgba(0, 0, 0, 0.55)
        cr.fill()
        cardart.draw_text(cr, text, cx, top + pad * 0.3, px, (0.1, 0.1, 0.1) if active else (1, 1, 1))

    def _draw_result(self, cr, hand, cx, cy, cw):
        colors = {
            BLACKJACK: (0.95, 0.75, 0.15),
            WIN: (0.20, 0.70, 0.35),
            PUSH: (0.45, 0.50, 0.55),
            SURRENDERED: (0.45, 0.50, 0.55),
        }
        bg = colors.get(hand.result, (0.80, 0.20, 0.22))
        net = hand.payout - hand.bet
        text = result_name(hand.result)
        if hand.result not in (PUSH,):
            text += f"  {money(net, signed=True)}"
        px = cw * 0.17
        tw, th = cardart.text_size(cr, text, px)
        bw, bh = tw + px * 1.2, th + px * 0.6
        cr.save()
        cardart.rounded_rect(cr, cx - bw / 2, cy - bh / 2, bw, bh, bh * 0.3)
        cr.set_source_rgba(*bg, 0.95)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.8)
        cr.set_line_width(max(1, cw * 0.015))
        cr.stroke()
        dark = hand.result == BLACKJACK
        cardart.draw_text(cr, text, cx, cy - th / 2, px, (0.1, 0.1, 0.1) if dark else (1, 1, 1))
        cr.restore()

    def _draw_banner(self, cr, text, cx, cy, cw, rgb, alpha):
        px = cw * 0.3
        tw, th = cardart.text_size(cr, text, px)
        bw, bh = tw + px * 1.4, th + px * 0.7
        cr.push_group()
        cardart.rounded_rect(cr, cx - bw / 2, cy - bh / 2, bw, bh, bh * 0.25)
        cr.set_source_rgba(0, 0, 0, 0.7)
        cr.fill()
        cardart.draw_text(cr, text, cx, cy - th / 2, px, rgb)
        cr.pop_group_to_source()
        cr.paint_with_alpha(alpha)

