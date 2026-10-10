#!/usr/bin/env bash
# Restore the instruction-only global Skill saved by the 2026-10-10 readiness repair.
# The current verified Skill is moved aside before the restore, so the operation
# remains recoverable. Run with the same account that owns ~/.codex.
set -euo pipefail
CURRENT="${ARCHCANVAS_GLOBAL_SKILL:-/home/fzg/.codex/skills/archcanvas}"
BACKUP="${1:-/tmp/archcanvas-global-before-20261010}"
if [[ ! -d "$BACKUP" || -L "$BACKUP" ]]; then
  echo "rollback backup is missing or is a symlink: $BACKUP" >&2
  exit 2
fi
if [[ ! -d "$(dirname "$CURRENT")" || -L "$(dirname "$CURRENT")" ]]; then
  echo "global Skill parent is missing or is a symlink: $(dirname "$CURRENT")" >&2
  exit 2
fi
if [[ ! -e "$CURRENT" && ! -L "$CURRENT" ]]; then
  mv "$BACKUP" "$CURRENT"
  echo "restored $CURRENT"
  exit 0
fi
STAGE="$(mktemp -d /tmp/archcanvas-global-rollback.XXXXXX)"
cleanup() { rmdir "$STAGE" 2>/dev/null || true; }
trap cleanup EXIT
mv "$CURRENT" "$STAGE/current"
if ! mv "$BACKUP" "$CURRENT"; then
  mv "$STAGE/current" "$CURRENT"
  echo "restore failed; current Skill was put back" >&2
  exit 1
fi
# Retain the replaced candidate for a subsequent restore or comparison.
echo "restored $CURRENT from $BACKUP"
echo "replaced Skill retained at $STAGE/current"
