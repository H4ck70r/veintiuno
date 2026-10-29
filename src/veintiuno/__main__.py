# SPDX-License-Identifier: GPL-3.0-or-later
"""Run from a source checkout: python3 -m veintiuno (from the src directory)."""

import os
import shutil
import subprocess
import sys
import tempfile


def _compile_translations() -> str | None:
    po_dir = os.path.join(os.path.dirname(__file__), "..", "..", "po")
    if not os.path.isdir(po_dir) or not shutil.which("msgfmt"):
        return None
    out = os.path.join(tempfile.gettempdir(), "veintiuno-locale")
    for name in os.listdir(po_dir):
        if name.endswith(".po"):
            target = os.path.join(out, name[:-3], "LC_MESSAGES")
            os.makedirs(target, exist_ok=True)
            subprocess.run(["msgfmt", "-o", os.path.join(target, "veintiuno.mo"),
                            os.path.join(po_dir, name)], check=False)
    return out


if __name__ == "__main__":
    from .main import main
    sys.exit(main(localedir=_compile_translations()))
