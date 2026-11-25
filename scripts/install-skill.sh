#!/usr/bin/env sh
# Installs the building-ai-agents skill for Claude Code and Codex (macOS, Linux, WSL).
#   scripts/install-skill.sh              install or update
#   scripts/install-skill.sh --uninstall  remove it (the copy is moved to the backups folder, not deleted)
# Existing copies are moved to ~/.claude/skill-backups (or ~/.codex/skill-backups), never deleted;
# backups stay outside the skills folder so they are not loaded as a second copy of the skill.
# Re-running with nothing changed makes no backup.
set -eu

src="$(cd "$(dirname "$0")/.." && pwd)/skill/building-ai-agents"
stamp="$(date +%Y%m%d-%H%M%S)"
mode="${1:-install}"

backup() {  # $1 = skills dir
  backups="$(dirname "$1")/skill-backups"
  mkdir -p "$backups"
  mv "$1/building-ai-agents" "$backups/building-ai-agents-$stamp"
  echo "existing copy moved to $backups/building-ai-agents-$stamp"
}

for dir in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
  dest="$dir/building-ai-agents"
  if [ "$mode" = "--uninstall" ]; then
    if [ -e "$dest" ]; then backup "$dir"; echo "uninstalled from $dir"; else echo "not installed in $dir"; fi
    continue
  fi
  mkdir -p "$dir"
  if [ -e "$dest" ]; then
    case "$dir" in
      "$HOME/.codex/"*) same=$(diff -rq -x evals -x __pycache__ "$src" "$dest" >/dev/null 2>&1 && echo yes || echo no) ;;
      *) same=$(diff -rq -x __pycache__ "$src" "$dest" >/dev/null 2>&1 && echo yes || echo no) ;;
    esac
    if [ "$same" = yes ]; then echo "up to date: $dest"; continue; fi
    backup "$dir"
  fi
  cp -R "$src" "$dest"
  case "$dir" in "$HOME/.codex/"*) rm -rf "$dest/evals" ;; esac  # the Codex folder only, not any path containing "codex"
  echo "installed to $dest"
done

[ "$mode" = "--uninstall" ] || echo "check: python3 \"$src/scripts/check_freshness.py\" --no-models"
