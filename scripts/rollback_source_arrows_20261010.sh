#!/usr/bin/env bash
# Restore the independently verified beta.8 Skill; retain the replaced version.
set -euo pipefail
PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$PROJECT/docs/evidence/source-dependency-arrows-20261010/switch-skill.py" \
  --source "$PROJECT/.archcanvas/source-arrows-beta8-rollback/.agents/skills/archcanvas" \
  --target /home/fzg/.codex/skills/archcanvas \
  --archive "$PROJECT/.archcanvas/backups/source-arrows-rollback-$(date +%Y%m%d-%H%M%S)"
