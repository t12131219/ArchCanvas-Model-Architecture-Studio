#!/usr/bin/env bash
# Restore verified beta.10 and retain the replaced Skill for recovery.
set -euo pipefail
PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$PROJECT/docs/evidence/source-dependency-arrows-20261010/switch-skill.py" \
  --source "$PROJECT/.archcanvas/source-boundary-beta10-rollback/.agents/skills/archcanvas" \
  --target /home/fzg/.codex/skills/archcanvas \
  --archive "$PROJECT/.archcanvas/backups/source-boundary-rollback-$(date +%Y%m%d-%H%M%S)"
