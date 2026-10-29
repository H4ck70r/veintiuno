# SPDX-License-Identifier: GPL-3.0-or-later
"""Application entry point."""

from __future__ import annotations

import gettext
import locale
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

APP_ID = "io.github.H4ck70r.Veintiuno"
VERSION = "1.1.0"
AUTHOR = 'Hector "H4CK70R" Mejia'

CSS = """
.table-controls {
  background-image: linear-gradient(to bottom, #12241b, #0c1712);
  border-top: 1px solid alpha(#f2cc6b, 0.25);
  color: #f3efe6;
}
.table-controls .dim-label { color: alpha(#f3efe6, 0.6); }

/* Casino buttons */
.casino-button {
  min-height: 44px;
  padding: 0 18px;
  border-radius: 14px;
  border: 1px solid alpha(white, 0.18);
  font-weight: 800;
  color: white;
  text-shadow: 0 1px 1px alpha(black, 0.35);
  background-image: linear-gradient(to bottom, #3d4a44, #27302c);
  box-shadow: inset 0 1px alpha(white, 0.22), 0 3px 0 alpha(black, 0.45),
              0 6px 14px alpha(black, 0.35);
  transition: transform 160ms cubic-bezier(0.2, 0.9, 0.3, 1.3), box-shadow 160ms ease-out,
              filter 160ms ease-out;
}
.casino-button:hover {
  transform: translateY(-2px);
  filter: brightness(1.1);
  box-shadow: inset 0 1px alpha(white, 0.25), 0 5px 0 alpha(black, 0.45),
              0 10px 20px alpha(black, 0.4);
}
.casino-button:active {
  transform: translateY(2px) scale(0.97);
  filter: brightness(0.95);
  box-shadow: inset 0 2px 4px alpha(black, 0.35), 0 1px 0 alpha(black, 0.45);
  transition-duration: 60ms;
}
.casino-button:disabled {
  filter: grayscale(1) brightness(0.8);
  opacity: 0.4;
  transform: none;
  box-shadow: none;
}
.casino-button:focus-visible { outline: 2px solid alpha(#f6d32d, 0.8); outline-offset: 2px; }
.casino-button .keycap {
  font-size: 0.75em;
  font-weight: 800;
  min-width: 14px;
  padding: 1px 5px;
  border-radius: 5px;
  background-color: alpha(black, 0.25);
  border: 1px solid alpha(white, 0.25);
  color: alpha(white, 0.9);
  text-shadow: none;
}
.casino-button.hit { background-image: linear-gradient(to bottom, #3ccf85, #1f8f57); }
.casino-button.stand { background-image: linear-gradient(to bottom, #ee4a52, #a51d2d); }
.casino-button.split { background-image: linear-gradient(to bottom, #4b93ee, #1a5fb4); }
.casino-button.surrender { background-image: linear-gradient(to bottom, #8e8a99, #57535f); }
.casino-button.double, .casino-button.deal {
  color: #2b1d00;
  text-shadow: 0 1px alpha(white, 0.35);
  background-image: linear-gradient(to bottom, #ffe27a, #e2a20c);
}
.casino-button.double .keycap, .casino-button.deal .keycap {
  color: #2b1d00;
  background-color: alpha(white, 0.35);
  border-color: alpha(#2b1d00, 0.25);
}
@keyframes deal-glow {
  0% { box-shadow: inset 0 1px alpha(white, 0.4), 0 3px 0 alpha(black, 0.45), 0 0 0 0 alpha(#ffd34d, 0.55); }
  70% { box-shadow: inset 0 1px alpha(white, 0.4), 0 3px 0 alpha(black, 0.45), 0 0 0 12px alpha(#ffd34d, 0); }
  100% { box-shadow: inset 0 1px alpha(white, 0.4), 0 3px 0 alpha(black, 0.45), 0 0 0 0 alpha(#ffd34d, 0); }
}
.casino-button.deal:not(:disabled) { animation: deal-glow 1.8s ease-out infinite; }
@keyframes pop-in {
  from { transform: translateY(10px) scale(0.92); opacity: 0; }
  to { transform: none; opacity: 1; }
}
.controls-page .casino-button { animation: pop-in 260ms cubic-bezier(0.2, 0.9, 0.3, 1.2); }
.controls-page .casino-button.deal:not(:disabled) {
  animation: pop-in 260ms cubic-bezier(0.2, 0.9, 0.3, 1.2), deal-glow 1.8s ease-out 260ms infinite;
}

/* Chips */
.chip-button {
  padding: 2px;
  min-width: 54px;
  min-height: 54px;
  transition: transform 180ms cubic-bezier(0.2, 0.9, 0.3, 1.4), filter 180ms ease-out;
}
.chip-button:hover { transform: translateY(-5px) rotate(-8deg); background: none; }
.chip-button:active { transform: translateY(1px) scale(0.9); transition-duration: 60ms; }
.chip-button:disabled { opacity: 0.3; filter: grayscale(0.8); transform: none; }

/* Card back gallery */
.back-option {
  padding: 4px;
  border-radius: 10px;
  transition: transform 160ms ease-out;
}
.back-option:hover { transform: translateY(-3px); }
.back-option:checked { box-shadow: 0 0 0 3px @accent_bg_color; }
"""


def setup_i18n(localedir: str | None) -> None:
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    if localedir:
        try:
            locale.bindtextdomain("veintiuno", localedir)
            locale.textdomain("veintiuno")
        except AttributeError:
            pass
        gettext.bindtextdomain("veintiuno", localedir)
    gettext.textdomain("veintiuno")


class Application(Adw.Application):
    def __init__(self):
        flags = Gio.ApplicationFlags.DEFAULT_FLAGS
        if os.environ.get("VEINTIUNO_SCREENSHOT"):
            # Scripted runs must not hand over to an instance the player has open.
            flags |= Gio.ApplicationFlags.NON_UNIQUE
        super().__init__(application_id=APP_ID, flags=flags)
        GLib.set_application_name("Veintiuno")
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS) if hasattr(provider, "load_from_string") else \
            provider.load_from_data(CSS.encode(), -1)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        for name, callback, accels in (
            ("preferences", self._on_preferences, ["<Control>comma"]),
            ("about", self._on_about, []),
            ("quit", self._on_quit, ["<Control>q"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            self.set_accels_for_action(f"app.{name}", accels)

    def do_activate(self):
        if self.window is None:
            from . import storage
            from .ui.window import Window
            self.window = Window(self, storage.load())
        self.window.present()
        if os.environ.get("VEINTIUNO_SCREENSHOT"):
            from . import devtools
            devtools.screenshot_script(self.window, os.environ["VEINTIUNO_SCREENSHOT"])

    def _on_preferences(self, *_args):
        if self.window and self.window.get_visible_dialog() is None:
            self.window.show_preferences()

    def _on_about(self, *_args):
        about = Adw.AboutDialog(
            application_name="Veintiuno",
            application_icon=APP_ID,
            developer_name=AUTHOR,
            version=VERSION,
            comments=gettext.gettext("A complete casino blackjack table for Linux"),
            website="https://github.com/H4ck70r/veintiuno",
            issue_url="https://github.com/H4ck70r/veintiuno/issues",
            license_type=Gtk.License.GPL_3_0,
            copyright=f"© 2026 {AUTHOR}",
            developers=[f"{AUTHOR} https://github.com/H4ck70r"],
            translator_credits=gettext.gettext("translator-credits"),
        )
        about.add_link(gettext.gettext("More by H4CK70R: wololo.top"), "https://wololo.top")
        about.add_link(gettext.gettext("More by H4CK70R: kontra.gg"), "https://kontra.gg")
        about.add_credit_section(gettext.gettext("Court Card Artwork"),
                                 ["Dmitry Fomin https://commons.wikimedia.org/wiki/User:Dmitry_Fomin"])
        about.add_legal_section(
            gettext.gettext("Court Card Artwork"), "Dmitry Fomin", Gtk.License.CUSTOM,
            gettext.gettext("The jack, queen and king images are the English pattern cards by "
                            "Dmitry Fomin, dedicated to the public domain under "
                            "<a href=\"https://creativecommons.org/publicdomain/zero/1.0/\">CC0 1.0</a>."))
        about.present(self.window)

    def _on_quit(self, *_args):
        if self.window:
            self.window.close()
        self.quit()


def main(version: str = VERSION, localedir: str | None = None) -> int:
    global VERSION
    VERSION = version
    setup_i18n(localedir)
    return Application().run(sys.argv)
