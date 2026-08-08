#!/usr/bin/env bash
# PreToolUse:Bash — advisory warn before git commit/push (pathspec / multi-stream).
# Installed by: sow-lint hooks install
set -uo pipefail
INPUT=$(cat 2>/dev/null || true)
case "$INPUT" in
  *"git commit"*|*"git push"*) ;;
  *) exit 0 ;;
esac
echo "--- ZEO pre-git check ---" >&2
CROSS=$(git diff --cached --name-only 2>/dev/null | grep -oE '(^|/)sow/[^/]+/' | sort -u | wc -l | tr -d ' ')
if [ "${CROSS:-0}" -gt 1 ]; then
  echo "WARNING: staged set spans $CROSS stream directories." >&2
  git diff --cached --name-only 2>/dev/null | head -8 >&2
  echo "Commit BY EXPLICIT PATHSPEC: git commit -m \"...\" -- <path>" >&2
fi
case "$INPUT" in
  *"git commit"*)
    case "$INPUT" in
      *" -- "*) ;;
      *) echo "WARNING: no explicit pathspec (-- <path>). A bare commit ships the whole index." >&2 ;;
    esac
  ;;
esac
exit 0
