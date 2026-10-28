#!/usr/bin/env sh
# Installs the building-ai-agents skill for Claude Code and Codex (macOS, Linux, WSL).
# Existing copies are moved to ~/.claude/skill-backups (or ~/.codex/skill-backups), never deleted;
# backups stay outside the skills folder so they are not loaded as a second copy of the skill.
set -eu

src="$(cd "$(dirname "$0")/.." && pwd)/skill/building-ai-agents"
stamp="$(date +%Y%m%d-%H%M%S)"

for dir in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
  mkdir -p "$dir"
  if [ -e "$dir/building-ai-agents" ]; then
    backups="$(dirname "$dir")/skill-backups"
    mkdir -p "$backups"
    mv "$dir/building-ai-agents" "$backups/building-ai-agents-$stamp"
    echo "existing copy moved to $backups/building-ai-agents-$stamp"
  fi
  cp -R "$src" "$dir/building-ai-agents"
  case "$dir" in *codex*) rm -rf "$dir/building-ai-agents/evals" ;; esac
  echo "installed to $dir/building-ai-agents"
done

echo "check: python3 \"$src/scripts/check_freshness.py\" --no-models"
