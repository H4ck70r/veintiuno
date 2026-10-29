# SPDX-License-Identifier: GPL-3.0-or-later
"""Sound effects, played through GTK's media backend when it is available."""

from __future__ import annotations

import os

from gi.repository import Gtk

SOUND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sounds")


class Sounds:
    def __init__(self):
        self.enabled = True
        self._playing: set[Gtk.MediaStream] = set()

    def play(self, name: str, volume: float = 0.7) -> None:
        if not self.enabled:
            return
        path = os.path.join(SOUND_DIR, f"{name}.wav")
        if not os.path.exists(path):
            return
        media = Gtk.MediaFile.new_for_filename(path)
        media.set_volume(volume)
        media.connect("notify::ended", self._on_ended)
        media.connect("notify::error", self._on_ended)
        self._playing.add(media)
        media.play()

    def _on_ended(self, media, _pspec) -> None:
        if media.get_ended() or media.get_error():
            self._playing.discard(media)
