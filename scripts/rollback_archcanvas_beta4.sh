#!/usr/bin/env bash
# Recover the previous verified global Skill after beta.4 activation.
set -euo pipefail
CURRENT="${ARCHCANVAS_GLOBAL_SKILL:-/home/fzg/.codex/skills/archcanvas}"
BACKUP="${1:-/tmp/archcanvas-global-beta3-before-beta4-20261010}"
if [[ ! -d "$BACKUP" || -L "$BACKUP" ]]; then echo "rollback backup is missing or is a symlink: $BACKUP" >&2; exit 2; fi
if [[ ! -d "$(dirname "$CURRENT")" || -L "$(dirname "$CURRENT")" ]]; then echo "global Skill parent is missing or is a symlink" >&2; exit 2; fi
STAGE="$(mktemp -d /tmp/archcanvas-beta4-rollback.XXXXXX)"
trap 'rmdir "$STAGE" 2>/dev/null || true' EXIT
if [[ -e "$CURRENT" || -L "$CURRENT" ]]; then mv "$CURRENT" "$STAGE/current"; fi
if ! mv "$BACKUP" "$CURRENT"; then
  [[ -e "$STAGE/current" ]] && mv "$STAGE/current" "$CURRENT"
  echo "restore failed; current Skill was put back" >&2
  exit 1
fi
# Keep the replaced beta.4 under /tmp/STAGE for recovery; the directory is
# deliberately retained when it contains files.
echo "restored $CURRENT from $BACKUP"
echo "replaced Skill retained at $STAGE/current"
