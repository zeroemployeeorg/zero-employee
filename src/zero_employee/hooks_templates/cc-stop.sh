#!/usr/bin/env bash
# Thin stub — logic lives in the zero-employee package (`zeo hooks stop`).
# Installed by: zeo hooks install. FAIL-OPEN when zeo is missing.
set -uo pipefail
ZEO=""
for c in "$(command -v zeo 2>/dev/null || true)" \
         "$HOME/.local/bin/zeo" \
         "$HOME/.local/share/uv/tools/zeo/bin/zeo" \
         "$HOME/.local/share/uv/tools/zero-employee/bin/zeo"; do
  if [ -n "$c" ] && [ -x "$c" ]; then ZEO="$c"; break; fi
done
[ -z "$ZEO" ] && exit 0
exec "$ZEO" hooks stop "$@"
