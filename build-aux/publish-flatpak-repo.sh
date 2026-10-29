#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Build Veintiuno and publish it to the signed Flatpak repository served by
# GitHub Pages (https://h4ck70r.github.io/veintiuno/), on the gh-pages branch.
#
# Needs: flatpak, org.flatpak.Builder (flatpak), gpg with the repository key,
# git with push access. Run from anywhere: build-aux/publish-flatpak-repo.sh
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
APP_ID=io.github.H4ck70r.Veintiuno
BRANCH=stable
BASE_URL=https://h4ck70r.github.io/veintiuno
KEY=${VEINTIUNO_GPG_KEY:-$(gpg --list-secret-keys --with-colons 'Veintiuno Flatpak Repository' \
    | awk -F: '/^fpr/ {print $10; exit}')}
PAGES="$ROOT/.pages"
BUILD_REPO="$ROOT/.repo-stable"

[ -n "$KEY" ] || { echo "No signing key found (set VEINTIUNO_GPG_KEY)." >&2; exit 1; }
cd "$ROOT"

# 1. Check out the gh-pages branch in .pages (created empty the first time).
if [ ! -d "$PAGES" ]; then
    git fetch -q origin gh-pages 2>/dev/null || true
    if git rev-parse -q --verify origin/gh-pages >/dev/null; then
        git worktree add -q "$PAGES" gh-pages
    else
        git worktree add -q --detach "$PAGES"
        (cd "$PAGES" && git checkout -q --orphan gh-pages && git rm -rqf .)
    fi
fi
(cd "$PAGES" && git pull -q --ff-only origin gh-pages 2>/dev/null || true)

# 2. Build into a local, unsigned repository.
flatpak run --filesystem="$ROOT" --cwd="$ROOT" org.flatpak.Builder \
    --force-clean --default-branch="$BRANCH" --repo="$BUILD_REPO" \
    --state-dir="$ROOT/.flatpak-builder" "$ROOT/build-dir" "$APP_ID.json"

# 3. Copy the commits into the published repository, signed.
if [ ! -d "$PAGES/repo" ]; then
    flatpak run --command=ostree --filesystem="$PAGES" org.flatpak.Builder \
        --repo="$PAGES/repo" init --mode=archive-z2
fi
for ref in $(flatpak repo --branches "$BUILD_REPO" | awk '{print $1}' | grep "/$BRANCH$"); do
    flatpak build-commit-from --src-repo="$BUILD_REPO" --src-ref="$ref" \
        --gpg-sign="$KEY" "$PAGES/repo" "$ref"
done
flatpak build-update-repo --gpg-sign="$KEY" --generate-static-deltas --prune \
    --prune-depth=3 --title="Veintiuno" --default-branch="$BRANCH" \
    --homepage=https://github.com/H4ck70r/veintiuno \
    --icon="$BASE_URL/icon.svg" "$PAGES/repo"

# 4. One-click install files and a small landing page.
GPGKEY=$(gpg --export "$KEY" | base64 -w0)
cat > "$PAGES/veintiuno.flatpakrepo" <<EOF
[Flatpak Repo]
Title=Veintiuno
Url=$BASE_URL/repo/
Homepage=https://github.com/H4ck70r/veintiuno
Comment=Blackjack para Linux por H4CK70R
Icon=$BASE_URL/icon.svg
GPGKey=$GPGKEY
EOF
cat > "$PAGES/$APP_ID.flatpakref" <<EOF
[Flatpak Ref]
Title=Veintiuno
Name=$APP_ID
Branch=$BRANCH
Url=$BASE_URL/repo/
SuggestRemoteName=veintiuno
Homepage=https://github.com/H4ck70r/veintiuno
Icon=$BASE_URL/icon.svg
RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo
IsRuntime=false
GPGKey=$GPGKEY
EOF
cp "$ROOT/data/icons/hicolor/scalable/apps/$APP_ID.svg" "$PAGES/icon.svg"
cp "$ROOT/data/screenshots/table.png" "$PAGES/table.png"
cp "$ROOT/build-aux/pages/index.html" "$PAGES/index.html"
touch "$PAGES/.nojekyll"

# 5. Publish.
cd "$PAGES"
git add -A
if git diff --cached --quiet; then
    echo "Nothing changed."
else
    VERSION=$(sed -n "s/^ *version: '\(.*\)',/\1/p" "$ROOT/meson.build")
    git commit -q -m "Publish Veintiuno $VERSION"
    git push -q origin gh-pages
    echo "Published Veintiuno $VERSION to $BASE_URL/"
fi
