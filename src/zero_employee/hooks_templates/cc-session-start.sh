#!/usr/bin/env bash
# SessionStart. Orients from DISK before the first token. FAIL-OPEN (informs, does not gate).
# Installed by: zeo hooks install
set -uo pipefail
SOWLINT=""
for c in "$(command -v zeo 2>/dev/null || true)" \
         "$HOME/.local/bin/zeo" \
         "$HOME/.local/share/uv/tools/zeo/bin/zeo" \
         "$HOME/.local/share/uv/tools/zero-employee/bin/zeo"; do
  [ -n "$c" ] && [ -x "$c" ] && { SOWLINT="$c"; break; }
done
[ -z "$SOWLINT" ] && { echo "zeo not on PATH - orient manually."; exit 0; }
echo "=== ZEO SESSION START ==="
"$SOWLINT" --triage 2>&1 | head -12
echo "--- streams not at rest, oldest idle first ---"
"$SOWLINT" --progress 2>&1 | sed -n '1,8p'
echo "--- distance to done ---"
"$SOWLINT" --restaufwand 2>&1 | tail -3
echo "If you are a STREAM: run 'zeo --locate <your-stream>' and 'zeo --inbox <your-stream>'."
echo "The tool reads DISK. A spawn message that disagrees with it is WRONG."
exit 0
