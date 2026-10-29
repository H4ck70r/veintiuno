# SPDX-License-Identifier: GPL-3.0-or-later
"""Casino-style buttons with drawn icons and key hints."""

from __future__ import annotations

import math

from gi.repository import Gtk

from . import cardart


def _card(cr, x, y, w, h, angle=0.0):
    cr.save()
    cr.translate(x + w / 2, y + h / 2)
    cr.rotate(angle)
    cardart.rounded_rect(cr, -w / 2, -h / 2, w, h, w * 0.18)
    cr.restore()


def draw_icon(cr, name: str, s: float, rgb=(1, 1, 1)) -> None:
    """Draw a white line icon in an s×s box. The source colour must be set."""
    lw = max(1.5, s * 0.09)
    cr.set_line_width(lw)
    cr.set_line_cap(1)  # round
    cr.set_line_join(1)
    if name == "hit":
        _card(cr, s * 0.12, s * 0.12, s * 0.48, s * 0.68)
        cr.stroke()
        cr.move_to(s * 0.72, s * 0.5)
        cr.line_to(s * 0.72, s * 0.9)
        cr.move_to(s * 0.52, s * 0.7)
        cr.line_to(s * 0.92, s * 0.7)
        cr.stroke()
    elif name == "stand":
        # An open palm.
        cardart.rounded_rect(cr, s * 0.28, s * 0.46, s * 0.46, s * 0.44, s * 0.16)
        cr.stroke()
        for i, top in enumerate((0.2, 0.1, 0.12, 0.22)):
            fx = s * (0.33 + i * 0.12)
            cr.move_to(fx, s * 0.48)
            cr.line_to(fx, s * top)
        cr.move_to(s * 0.29, s * 0.66)
        cr.line_to(s * 0.12, s * 0.48)
        cr.stroke()
    elif name == "double":
        cardart.draw_text(cr, "×2", s * 0.5, s * 0.08, s * 0.72, rgb)
    elif name == "split":
        _card(cr, s * 0.06, s * 0.2, s * 0.36, s * 0.52, -0.25)
        cr.stroke()
        _card(cr, s * 0.58, s * 0.2, s * 0.36, s * 0.52, 0.25)
        cr.stroke()
        cr.move_to(s * 0.5, s * 0.14)
        cr.line_to(s * 0.5, s * 0.88)
        cr.stroke()
    elif name == "surrender":
        cr.move_to(s * 0.24, s * 0.92)
        cr.line_to(s * 0.24, s * 0.1)
        cr.stroke()
        cr.move_to(s * 0.24, s * 0.12)
        cr.curve_to(s * 0.45, s * 0.02, s * 0.6, s * 0.28, s * 0.86, s * 0.16)
        cr.line_to(s * 0.86, s * 0.54)
        cr.curve_to(s * 0.6, s * 0.66, s * 0.45, s * 0.4, s * 0.24, s * 0.5)
        cr.close_path()
        cr.fill()
    elif name == "deal":
        for i, angle in enumerate((-0.35, 0.0, 0.35)):
            _card(cr, s * (0.22 + i * 0.14), s * 0.16, s * 0.34, s * 0.5, angle)
            cr.stroke()
        cr.move_to(s * 0.3, s * 0.86)
        cr.line_to(s * 0.7, s * 0.86)
        cr.stroke()
    elif name == "rebet":
        cr.arc(s * 0.5, s * 0.52, s * 0.32, math.radians(-60), math.radians(240))
        cr.stroke()
        tip_x, tip_y = s * 0.5 + s * 0.32 * math.cos(math.radians(-60)), s * 0.52 + s * 0.32 * math.sin(math.radians(-60))
        cr.move_to(tip_x - s * 0.2, tip_y - s * 0.02)
        cr.line_to(tip_x, tip_y)
        cr.line_to(tip_x - s * 0.02, tip_y + s * 0.2)
        cr.stroke()
    elif name == "clear":
        cr.move_to(s * 0.22, s * 0.22)
        cr.line_to(s * 0.78, s * 0.78)
        cr.move_to(s * 0.78, s * 0.22)
        cr.line_to(s * 0.22, s * 0.78)
        cr.stroke()
    elif name in ("insurance", "even-money"):
        cr.move_to(s * 0.5, s * 0.08)
        cr.line_to(s * 0.86, s * 0.22)
        cr.curve_to(s * 0.86, s * 0.6, s * 0.7, s * 0.82, s * 0.5, s * 0.94)
        cr.curve_to(s * 0.3, s * 0.82, s * 0.14, s * 0.6, s * 0.14, s * 0.22)
        cr.close_path()
        cr.stroke()
        cr.move_to(s * 0.34, s * 0.5)
        cr.line_to(s * 0.46, s * 0.62)
        cr.line_to(s * 0.68, s * 0.38)
        cr.stroke()
    elif name == "decline":
        cr.arc(s * 0.5, s * 0.5, s * 0.36, 0, 2 * math.pi)
        cr.stroke()
        cr.move_to(s * 0.25, s * 0.75)
        cr.line_to(s * 0.75, s * 0.25)
        cr.stroke()
    elif name == "rebuy":
        cardart.draw_text(cr, "$", s * 0.5, s * 0.02, s * 0.8, rgb)


class ActionButton(Gtk.Button):
    """A pill button with a drawn icon, a label and a keycap hint."""

    def __init__(self, label: str, action: str, icon: str, style: str,
                 key: str | None = None, tooltip: str | None = None):
        super().__init__(action_name=action)
        self.add_css_class("casino-button")
        self.add_css_class(style)
        self.icon = icon

        box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        area = Gtk.DrawingArea(content_width=20, content_height=20, valign=Gtk.Align.CENTER)
        area.add_css_class("button-icon")
        area.set_draw_func(self._draw_icon)
        self._area = area
        box.append(area)

        self.label = Gtk.Label(label=label, use_underline=True)
        self.label.set_mnemonic_widget(self)
        box.append(self.label)

        if key:
            keycap = Gtk.Label(label=key, valign=Gtk.Align.CENTER)
            keycap.add_css_class("keycap")
            box.append(keycap)
        self.set_child(box)
        if tooltip:
            self.set_tooltip_text(tooltip)

    def set_label_text(self, text: str) -> None:
        self.label.set_label(text)

    def set_icon(self, icon: str) -> None:
        self.icon = icon
        self._area.queue_draw()

    def _draw_icon(self, area, cr, width, height):
        color = area.get_color()
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        draw_icon(cr, self.icon, min(width, height), (color.red, color.green, color.blue))
