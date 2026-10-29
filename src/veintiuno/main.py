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
VERSION = "1.0.0"
AUTHOR = 'Hector "H4CK70R" Mejia'

CSS = """
.table-controls {
  background-color: color-mix(in srgb, @window_bg_color 92%, #0b3d24);
  border-top: 1px solid alpha(black, 0.15);
}
.chip-button {
  padding: 2px;
  min-width: 54px;
  min-height: 54px;
}
.chip-button:disabled {
  opacity: 0.35;
}
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
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
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
