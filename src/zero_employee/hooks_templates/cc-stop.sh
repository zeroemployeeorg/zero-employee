#!/usr/bin/env bash
# Stop. Advisory: a blocked stop strands work. Logs session cost via zeo (no local rates).
# Installed by: zeo hooks install
set -uo pipefail
LOG=tools/stream-instruments/session-costs.jsonl
INPUT=$(cat 2>/dev/null || true)
mkdir -p "$(dirname "$LOG")"

SOWLINT=""
for c in "$(command -v zeo 2>/dev/null || true)" \
         "$HOME/.local/bin/zeo" \
         "$HOME/.local/share/uv/tools/zeo/bin/zeo" \
         "$HOME/.local/share/uv/tools/zero-employee/bin/zeo"; do
  [ -n "$c" ] && [ -x "$c" ] && { SOWLINT="$c"; break; }
done

TP=$(printf '%s\n' "$INPUT" | python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read() or "{}")
except Exception:
    d = {}
print(d.get("transcript_path") or "")
' 2>/dev/null || true)

if [ -n "$SOWLINT" ] && [ -n "$TP" ] && [ -f "$TP" ]; then
  "$SOWLINT" --session-cost --transcript "$TP" --append-cost-log "$LOG" >/dev/null 2>&1 || true
elif [ -n "$SOWLINT" ] && [ -f "$LOG" ]; then
  "$SOWLINT" --session-cost --cost-log "$LOG" >/dev/null 2>&1 || true
fi

UNCOMMITTED=$(git status --short 2>/dev/null | grep -cE '(^|/)(sow|ruling)/.*\.md$' || true)
if [ "${UNCOMMITTED:-0}" -gt 0 ]; then
  echo "ZEO: ${UNCOMMITTED} SOW/ruling file(s) UNCOMMITTED. Your context dies here; the chain is what survives." >&2
  git status --short | grep -E '(^|/)(sow|ruling)/.*\.md$' | head -5 >&2
fi
exit 0
