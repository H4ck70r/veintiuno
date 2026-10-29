# SPDX-License-Identifier: GPL-3.0-or-later
"""Scripted screenshots for development and the AppStream listing.

VEINTIUNO_SCREENSHOT=<dir> VEINTIUNO_SCRIPT="w:800,s:betting,a:chip:25,a:deal,w:2500,s:dealt"
  w:<ms>            wait
  s:<name>          save <dir>/<name>.png
  a:<action>[:int]  activate win.<action>
  p:<app action>    activate app.<action>
  page:<name>       show a page of the open preferences dialog
VEINTIUNO_SEED=<int> makes the shoe deterministic.
"""

import os
import random

import gi

gi.require_version("Graphene", "1.0")
from gi.repository import GLib, Graphene, Gtk  # noqa: E402

from .engine.cards import Card, Shoe  # noqa: E402


def snap(window: Gtk.Window, path: str) -> None:
    width, height = window.get_width(), window.get_height()
    paintable = Gtk.WidgetPaintable.new(window)
    snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, width, height)
    node = snapshot.to_node()
    if node is None:
        print("nothing to snapshot", path, flush=True)
        return
    rect = Graphene.Rect().init(0, 0, width, height)
    texture = window.get_renderer().render_texture(node, rect)
    if not texture.save_to_png(path):
        print("could not save", path, flush=True)


def screenshot_script(window, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    seed = os.environ.get("VEINTIUNO_SEED")
    if seed:
        game = window.game
        game.rng = random.Random(int(seed))
        game.shoe = Shoe(game.rules.decks, game.rules.penetration, game.rng)
        window.table.set_game(game)
    stack = os.environ.get("VEINTIUNO_STACK")
    if stack:
        window.game.shoe.stack([Card(int(r), i % 4) for i, r in enumerate(stack.split("-"))])
    size = os.environ.get("VEINTIUNO_SIZE")
    if size:
        w, h = (int(v) for v in size.split("x"))
        window.set_default_size(w, h)
    steps = [s for s in os.environ.get("VEINTIUNO_SCRIPT", "w:1000,s:window").split(",") if s]

    def run_next():
        while steps:
            kind, _, arg = steps.pop(0).partition(":")
            if kind == "w":
                GLib.timeout_add(int(arg), run_next)
                return False
            if kind == "s":
                snap(window, os.path.join(out_dir, f"{arg}.png"))
                print("screenshot", arg, flush=True)
            elif kind == "a":
                name, _, param = arg.partition(":")
                target = GLib.Variant("i", int(param)) if param else None
                if window.lookup_action(name) is None:
                    print("unknown action", name, flush=True)
                    continue
                window.activate_action(f"win.{name}", target)
                print("action", arg, "phase", window.game.phase, flush=True)
            elif kind == "p":
                window.get_application().activate_action(arg, None)
            elif kind == "page":
                window.get_visible_dialog().set_visible_page_name(arg)
        window.get_application().quit()
        return False

    GLib.idle_add(run_next)
