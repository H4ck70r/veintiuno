#!/bin/sh
# Run Veintiuno from the source tree inside the GNOME runtime (no install needed).
# Extra environment can be passed as VAR=value arguments.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ENVS=""
for kv in "$@"; do ENVS="$ENVS --env=$kv"; done
exec flatpak run --command=python3 --share=ipc --socket=x11 --socket=wayland \
  --device=dri --socket=session-bus --filesystem="$ROOT" ${DEV_EXTRA_FS:+--filesystem=$DEV_EXTRA_FS} \
  $ENVS --cwd="$ROOT/src" org.gnome.Platform//51 -m veintiuno
