#!/usr/bin/env bash
# Restore the verified beta.11 Skill; archive the currently installed Skill.
set -euo pipefail
PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$PROJECT/docs/evidence/source-dependency-arrows-20261010/switch-skill.py" \
  --source "$PROJECT/.archcanvas/backups/global-skill-before-rebuild-beta12-20261010" \
  --target /home/fzg/.codex/skills/archcanvas \
  --archive "$PROJECT/.archcanvas/backups/rebuild-rollback-$(date +%Y%m%d-%H%M%S)"
