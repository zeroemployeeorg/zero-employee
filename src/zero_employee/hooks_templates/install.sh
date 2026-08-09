#!/usr/bin/env bash
# Re-install the pre-commit gate into .git/hooks from tools/hooks/pre-commit.
# Prefer: zeo hooks install
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_SRC="$REPO_ROOT/tools/hooks/pre-commit"
HOOK_DST="$REPO_ROOT/.git/hooks/pre-commit"
cp "$HOOK_SRC" "$HOOK_DST" && chmod +x "$HOOK_DST"
echo "installed: $HOOK_DST"
SL="$(command -v zeo 2>/dev/null || echo "$HOME/.local/bin/zeo")"
if "$SL" --help 2>&1 | grep -q .; then echo "zeo resolves: $SL"; fi
echo "gate live: staged sow/ + ruling/ .md must PASS."
