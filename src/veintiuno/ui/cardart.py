# SPDX-License-Identifier: GPL-3.0-or-later
"""Vector drawing of cards, suits and chips with Cairo."""

from __future__ import annotations

import math
import os

import cairo
import gi

gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Pango, PangoCairo  # noqa: E402

try:
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg  # noqa: E402
except (ValueError, ImportError):
    Rsvg = None

from .. import storage  # noqa: E402
from ..engine.cards import CLUBS, DIAMONDS, HEARTS, SPADES  # noqa: E402

COURT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cards")
COURT_NAMES = {11: "jack", 12: "queen", 13: "king"}
SUIT_NAMES = {SPADES: "spades", HEARTS: "hearts", DIAMONDS: "diamonds", CLUBS: "clubs"}
COURT_SIZE = (360, 540)  # size of the court card SVG documents
_court_handles: dict = {}
_court_cache: dict = {}
_back_cache: dict = {}
PACK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backs")
_scaled_cache: dict = {}

RED = (0.80, 0.10, 0.16)
BLACK = (0.10, 0.10, 0.12)
CARD_FACE = (0.99, 0.98, 0.96)
BACKS = {
    "red": (0.62, 0.08, 0.12),
    "blue": (0.10, 0.24, 0.55),
    "green": (0.06, 0.40, 0.25),
}
CHIP_COLORS = {
    1: ((0.93, 0.93, 0.90), (0.25, 0.30, 0.55)),
    5: ((0.78, 0.12, 0.14), (0.98, 0.95, 0.90)),
    25: ((0.10, 0.52, 0.28), (0.98, 0.95, 0.90)),
    100: ((0.12, 0.12, 0.14), (0.98, 0.95, 0.90)),
    500: ((0.45, 0.20, 0.62), (0.98, 0.95, 0.90)),
    1000: ((0.93, 0.62, 0.10), (0.20, 0.12, 0.05)),
}
CHIP_VALUES = (1000, 500, 100, 25, 5, 1)

FONT = "Cantarell, DejaVu Sans, Sans"


def rounded_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def suit_path(cr, suit, cx, cy, size):
    """Add a suit outline centred on (cx, cy) fitting a size×size box."""
    cr.save()
    cr.translate(cx, cy)
    cr.scale(size, size)
    if suit == HEARTS:
        cr.move_to(0, 0.45)
        cr.curve_to(-0.15, 0.30, -0.5, 0.10, -0.5, -0.15)
        cr.curve_to(-0.5, -0.42, -0.18, -0.52, 0, -0.25)
        cr.curve_to(0.18, -0.52, 0.5, -0.42, 0.5, -0.15)
        cr.curve_to(0.5, 0.10, 0.15, 0.30, 0, 0.45)
        cr.close_path()
    elif suit == DIAMONDS:
        cr.move_to(0, -0.5)
        cr.curve_to(0.12, -0.3, 0.25, -0.15, 0.38, 0)
        cr.curve_to(0.25, 0.15, 0.12, 0.3, 0, 0.5)
        cr.curve_to(-0.12, 0.3, -0.25, 0.15, -0.38, 0)
        cr.curve_to(-0.25, -0.15, -0.12, -0.3, 0, -0.5)
        cr.close_path()
    elif suit == SPADES:
        cr.move_to(0, -0.5)
        cr.curve_to(-0.15, -0.30, -0.5, -0.12, -0.5, 0.12)
        cr.curve_to(-0.5, 0.36, -0.2, 0.42, -0.04, 0.22)
        cr.line_to(-0.16, 0.5)
        cr.line_to(0.16, 0.5)
        cr.line_to(0.04, 0.22)
        cr.curve_to(0.2, 0.42, 0.5, 0.36, 0.5, 0.12)
        cr.curve_to(0.5, -0.12, 0.15, -0.30, 0, -0.5)
        cr.close_path()
    else:  # clubs
        for x, y in ((0, -0.26), (-0.25, 0.08), (0.25, 0.08)):
            cr.new_sub_path()
            cr.arc(x, y, 0.22, 0, 2 * math.pi)
        cr.new_sub_path()
        cr.arc(0, 0.02, 0.12, 0, 2 * math.pi)
        cr.move_to(-0.03, 0.05)
        cr.line_to(-0.16, 0.5)
        cr.line_to(0.16, 0.5)
        cr.line_to(0.03, 0.05)
        cr.close_path()
    cr.restore()


def draw_suit(cr, suit, cx, cy, size, flip=False):
    cr.save()
    if flip:
        cr.translate(cx, cy)
        cr.rotate(math.pi)
        cx = cy = 0
    cr.set_source_rgb(*(RED if suit in (HEARTS, DIAMONDS) else BLACK))
    suit_path(cr, suit, cx, cy, size)
    cr.set_fill_rule(0)  # winding, so overlapping club lobes stay solid
    cr.fill()
    cr.restore()


def draw_text(cr, text, x, y, px, rgb, weight="Bold", align="center", family=FONT):
    """Draw text horizontally aligned on x with its top at y. Returns height."""
    layout = PangoCairo.create_layout(cr)
    desc = Pango.FontDescription.from_string(f"{family} {weight}")
    desc.set_absolute_size(max(px, 1) * Pango.SCALE)
    layout.set_font_description(desc)
    layout.set_text(text, -1)
    _ink, logical = layout.get_pixel_extents()
    if align == "center":
        x -= logical.width / 2
    elif align == "right":
        x -= logical.width
    cr.set_source_rgb(*rgb)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    return logical.height


def text_size(cr, text, px, weight="Bold"):
    layout = PangoCairo.create_layout(cr)
    desc = Pango.FontDescription.from_string(f"{FONT} {weight}")
    desc.set_absolute_size(max(px, 1) * Pango.SCALE)
    layout.set_font_description(desc)
    layout.set_text(text, -1)
    _ink, logical = layout.get_pixel_extents()
    return logical.width, logical.height


PIPS = {
    2: [(.5, 0), (.5, 1)],
    3: [(.5, 0), (.5, .5), (.5, 1)],
    4: [(0, 0), (1, 0), (0, 1), (1, 1)],
    5: [(0, 0), (1, 0), (.5, .5), (0, 1), (1, 1)],
    6: [(0, 0), (1, 0), (0, .5), (1, .5), (0, 1), (1, 1)],
    7: [(0, 0), (1, 0), (.5, .25), (0, .5), (1, .5), (0, 1), (1, 1)],
    8: [(0, 0), (1, 0), (.5, .25), (0, .5), (1, .5), (.5, .75), (0, 1), (1, 1)],
    9: [(0, 0), (1, 0), (0, 1 / 3), (1, 1 / 3), (.5, .5), (0, 2 / 3), (1, 2 / 3), (0, 1), (1, 1)],
    10: [(0, 0), (1, 0), (.5, 1 / 6), (0, 1 / 3), (1, 1 / 3), (0, 2 / 3), (1, 2 / 3),
         (.5, 5 / 6), (0, 1), (1, 1)],
}


def _court_surface(card, w, h, scale):
    """Render a court card SVG at the card's pixel size (cached)."""
    if Rsvg is None:
        return None
    pw, ph = max(1, round(w * scale)), max(1, round(h * scale))
    key = (card.rank, card.suit, pw, ph)
    surface = _court_cache.get(key)
    if surface is not None:
        return surface
    path = os.path.join(COURT_DIR, f"{COURT_NAMES[card.rank]}_{SUIT_NAMES[card.suit]}.svg")
    handle = _court_handles.get(path)
    if handle is None:
        try:
            handle = Rsvg.Handle.new_from_file(path)
        except GLib.Error:
            return None
        _court_handles[path] = handle
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, pw, ph)
    ctx = cairo.Context(surface)
    ctx.scale(pw / COURT_SIZE[0], ph / COURT_SIZE[1])
    viewport = Rsvg.Rectangle()
    viewport.x, viewport.y = 0, 0
    viewport.width, viewport.height = COURT_SIZE
    try:
        handle.render_document(ctx, viewport)
    except GLib.Error:
        return None
    if len(_court_cache) > 64:
        _court_cache.clear()
    _court_cache[key] = surface
    return surface


def _draw_court_art(cr, card, x, y, w, h, scale) -> bool:
    surface = _court_surface(card, w, h, scale)
    if surface is None:
        return False
    r = w * 0.08
    cr.save()
    rounded_rect(cr, x, y, w, h, r)
    cr.set_source_rgb(1, 1, 1)
    cr.fill_preserve()
    cr.clip()
    cr.translate(x, y)
    cr.scale(1 / scale, 1 / scale)
    cr.set_source_surface(surface, 0, 0)
    cr.paint()
    cr.restore()
    rounded_rect(cr, x, y, w, h, r)
    cr.set_source_rgba(0, 0, 0, 0.25)
    cr.set_line_width(max(1, w * 0.012))
    cr.stroke()
    return True


def draw_card_face(cr, card, x, y, w, h, scale=1):
    if card.rank > 10 and _draw_court_art(cr, card, x, y, w, h, scale):
        return
    color = RED if card.is_red else BLACK
    r = w * 0.08
    rounded_rect(cr, x, y, w, h, r)
    cr.set_source_rgb(*CARD_FACE)
    cr.fill_preserve()
    cr.set_source_rgba(0, 0, 0, 0.25)
    cr.set_line_width(max(1, w * 0.012))
    cr.stroke()

    # Corner indices, top-left and rotated bottom-right.
    index_px = w * 0.2
    for flip in (False, True):
        cr.save()
        if flip:
            cr.translate(x + w, y + h)
            cr.rotate(math.pi)
            ox, oy = 0, 0
        else:
            ox, oy = x, y
        cx = ox + w * 0.13
        th = draw_text(cr, card.label, cx, oy + h * 0.035, index_px, color)
        draw_suit(cr, card.suit, cx, oy + h * 0.035 + th * 0.95, w * 0.12)
        cr.restore()

    # Centre.
    left, right = x + w * 0.3, x + w * 0.7
    top, bottom = y + h * 0.2, y + h * 0.8
    if card.rank == 1:
        size = w * (0.52 if card.suit == SPADES else 0.4)
        draw_suit(cr, card.suit, x + w / 2, y + h / 2, size)
    elif card.rank <= 10:
        pip = w * 0.19
        for px, py in PIPS[card.rank]:
            draw_suit(cr, card.suit, left + (right - left) * px, top + (bottom - top) * py,
                      pip, flip=py > 0.5)
    else:
        fx, fy, fw, fh = x + w * 0.22, y + h * 0.15, w * 0.56, h * 0.7
        rounded_rect(cr, fx, fy, fw, fh, w * 0.04)
        tint = (0.98, 0.93, 0.80) if not card.is_red else (0.99, 0.90, 0.88)
        cr.set_source_rgb(*tint)
        cr.fill_preserve()
        cr.set_source_rgb(*color)
        cr.set_line_width(max(1, w * 0.015))
        cr.stroke()
        # Simple crown/ornament band.
        cr.set_source_rgb(0.85, 0.65, 0.15)
        band_y = fy + fh * 0.12
        for i in range(5):
            bx = fx + fw * (0.15 + 0.175 * i)
            cr.move_to(bx, band_y + fh * 0.08)
            cr.line_to(bx + fw * 0.0875, band_y - fh * (0.02 if i % 2 else 0.06))
            cr.line_to(bx + fw * 0.175, band_y + fh * 0.08)
        cr.close_path()
        cr.fill()
        draw_text(cr, card.label, fx + fw / 2, fy + fh * 0.22, fw * 0.62, color,
                  family="DejaVu Serif, Serif")
        draw_suit(cr, card.suit, fx + fw / 2, fy + fh * 0.78, fw * 0.36)


def texture_surface(texture: Gdk.Texture) -> cairo.ImageSurface:
    """Convert a GdkTexture into a Cairo image surface."""
    downloader = Gdk.TextureDownloader.new(texture)
    downloader.set_format(Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED)
    data, stride = downloader.download_bytes()
    return cairo.ImageSurface.create_for_data(bytearray(data.get_data()), cairo.FORMAT_ARGB32,
                                              texture.get_width(), texture.get_height(), stride)


def _load_back(back: str):
    """Full-size image of a bundled or custom back, or None."""
    if back in storage.PACK_BACKS:
        path = os.path.join(PACK_DIR, f"{back}.jpg")
    elif back.startswith("custom:"):
        path = os.path.join(storage.backs_dir(), back.split(":", 1)[1])
    else:
        return None
    surface = _back_cache.get(path)
    if surface is None:
        try:
            surface = texture_surface(Gdk.Texture.new_from_filename(path))
        except GLib.Error:
            return None
        _back_cache[path] = surface
    return surface


def custom_back_surface(back: str, w: float = 0, h: float = 0, scale: float = 1):
    """Image for a bundled or custom ("custom:<file>") back, pre-scaled to w×h points."""
    source = _load_back(back)
    if source is None or w <= 0 or h <= 0:
        return source
    pw, ph = max(1, round(w * scale)), max(1, round(h * scale))
    key = (back, pw, ph)
    surface = _scaled_cache.get(key)
    if surface is None:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, pw, ph)
        ctx = cairo.Context(surface)
        sw, sh = source.get_width(), source.get_height()
        fit = max(pw / sw, ph / sh)
        ctx.translate((pw - sw * fit) / 2, (ph - sh * fit) / 2)
        ctx.scale(fit, fit)
        ctx.set_source_surface(source, 0, 0)
        ctx.get_source().set_filter(cairo.FILTER_BEST)
        ctx.paint()
        if len(_scaled_cache) > 48:
            _scaled_cache.clear()
        _scaled_cache[key] = surface
    return surface


def forget_custom_back(back: str) -> None:
    _back_cache.pop(os.path.join(storage.backs_dir(), back.split(":", 1)[-1]), None)
    for key in [k for k in _scaled_cache if k[0] == back]:
        del _scaled_cache[key]


def draw_card_back(cr, x, y, w, h, back="red", scale=1):
    r = w * 0.08
    rounded_rect(cr, x, y, w, h, r)
    cr.set_source_rgb(*CARD_FACE)
    cr.fill_preserve()
    cr.set_source_rgba(0, 0, 0, 0.25)
    cr.set_line_width(max(1, w * 0.012))
    cr.stroke()

    m = w * 0.028
    ix, iy, iw, ih = x + m, y + m, w - 2 * m, h - 2 * m
    image = custom_back_surface(back, iw, ih, scale)
    if image is not None:
        cr.save()
        rounded_rect(cr, ix, iy, iw, ih, r * 0.75)
        cr.clip()
        iw0, ih0 = image.get_width(), image.get_height()
        fit = max(iw / iw0, ih / ih0)
        cr.translate(ix + (iw - iw0 * fit) / 2, iy + (ih - ih0 * fit) / 2)
        cr.scale(fit, fit)
        cr.set_source_surface(image, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_GOOD)
        cr.paint()
        cr.restore()
        rounded_rect(cr, ix, iy, iw, ih, r * 0.75)
        cr.set_source_rgba(0, 0, 0, 0.2)
        cr.set_line_width(max(1, w * 0.01))
        cr.stroke()
        return
    base = BACKS.get(back, BACKS["red"])
    cr.save()
    rounded_rect(cr, ix, iy, iw, ih, r * 0.75)
    cr.clip_preserve()
    cr.set_source_rgb(*base)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.22)
    cr.set_line_width(max(1, w * 0.012))
    step = w * 0.09
    n = int((iw + ih) / step) + 2
    for i in range(n):
        o = i * step
        cr.move_to(ix + o, iy)
        cr.line_to(ix + o - ih, iy + ih)
        cr.move_to(ix + o - ih, iy)
        cr.line_to(ix + o, iy + ih)
    cr.stroke()
    # Centre medallion.
    cr.set_source_rgb(*base)
    cr.arc(x + w / 2, y + h / 2, w * 0.2, 0, 2 * math.pi)
    cr.fill_preserve()
    cr.set_source_rgba(1, 1, 1, 0.7)
    cr.set_line_width(max(1, w * 0.02))
    cr.stroke()
    draw_text(cr, "21", x + w / 2, y + h / 2 - w * 0.11, w * 0.16, (1, 1, 1))
    cr.restore()
    rounded_rect(cr, ix, iy, iw, ih, r * 0.75)
    cr.set_source_rgba(1, 1, 1, 0.6)
    cr.set_line_width(max(1, w * 0.015))
    cr.stroke()


def draw_card(cr, card, x, y, w, h, face_up, back="red", flip=1.0, alpha=1.0, highlight=False,
              scale=1):
    """Draw a card at (x, y). `flip` in [-1, 1] squeezes it horizontally."""
    cr.save()
    cx = x + w / 2
    cr.translate(cx, 0)
    cr.scale(max(abs(flip), 0.001), 1)
    cr.translate(-cx, 0)
    if alpha < 1:
        cr.push_group()
    # Shadow.
    rounded_rect(cr, x + w * 0.03, y + w * 0.05, w, h, w * 0.08)
    cr.set_source_rgba(0, 0, 0, 0.28)
    cr.fill()
    if face_up and card is not None:
        draw_card_face(cr, card, x, y, w, h, scale)
    else:
        draw_card_back(cr, x, y, w, h, back, scale)
    if highlight:
        rounded_rect(cr, x - 2, y - 2, w + 4, h + 4, w * 0.1)
        cr.set_source_rgba(1.0, 0.85, 0.3, 0.9)
        cr.set_line_width(max(2, w * 0.03))
        cr.stroke()
    if alpha < 1:
        cr.pop_group_to_source()
        cr.paint_with_alpha(alpha)
    cr.restore()


def chips_for(amount: float) -> list[int]:
    """Break an amount into chip denominations, largest first."""
    chips = []
    rest = int(amount)
    for value in CHIP_VALUES:
        while rest >= value and len(chips) < 14:
            chips.append(value)
            rest -= value
    return chips


def draw_chip(cr, cx, cy, radius, value, label=True):
    body, accent = CHIP_COLORS.get(value, CHIP_COLORS[1])
    cr.save()
    cr.arc(cx + radius * 0.06, cy + radius * 0.1, radius, 0, 2 * math.pi)
    cr.set_source_rgba(0, 0, 0, 0.3)
    cr.fill()
    cr.arc(cx, cy, radius, 0, 2 * math.pi)
    cr.set_source_rgb(*body)
    cr.fill()
    # Edge spots.
    cr.set_source_rgb(*accent)
    for i in range(6):
        a = i * math.pi / 3
        cr.arc(cx, cy, radius * 0.86, a - 0.18, a + 0.18)
        cr.arc_negative(cx, cy, radius * 0.66, a + 0.18, a - 0.18)
        cr.close_path()
        cr.fill()
    cr.arc(cx, cy, radius * 0.56, 0, 2 * math.pi)
    cr.set_line_width(max(1, radius * 0.06))
    cr.stroke()
    if label:
        text = f"{value // 1000}K" if value >= 1000 else str(value)
        draw_text(cr, text, cx, cy - radius * 0.3, radius * 0.5, accent)
    cr.restore()
