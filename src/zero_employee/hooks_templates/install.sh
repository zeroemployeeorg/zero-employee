#!/usr/bin/env bash
# Re-install thin hook stubs via the package. Prefer: zeo hooks install
set -euo pipefail
ZEO=""
for c in "$(command -v zeo 2>/dev/null || true)" \
         "$HOME/.local/bin/zeo" \
         "$HOME/.local/share/uv/tools/zeo/bin/zeo" \
         "$HOME/.local/share/uv/tools/zero-employee/bin/zeo"; do
  if [ -n "$c" ] && [ -x "$c" ]; then ZEO="$c"; break; fi
done
if [ -z "$ZEO" ]; then
  echo "zeo not found; cannot reinstall hooks." >&2
  exit 1
fi
exec "$ZEO" hooks install "$@"
