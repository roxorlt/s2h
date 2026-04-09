#!/usr/bin/env bash
set -euo pipefail

S2H_DIR="$HOME/.claude/skills/s2h"
REPO="https://github.com/roxorlt/s2h.git"

echo "Installing s2h (Skill-to-HTML)..."

if [ -d "$S2H_DIR/.git" ]; then
  echo "Updating existing installation..."
  git -C "$S2H_DIR" pull origin main
else
  if [ -d "$S2H_DIR" ]; then
    echo "Backing up existing $S2H_DIR to ${S2H_DIR}.bak"
    mv "$S2H_DIR" "${S2H_DIR}.bak"
  fi
  mkdir -p "$(dirname "$S2H_DIR")"
  git clone "$REPO" "$S2H_DIR"
fi

echo ""
echo "Installed s2h v$(cat "$S2H_DIR/VERSION") to $S2H_DIR"
echo ""
echo "Usage:"
echo "  /s2h ~/.claude/skills/some-skill/SKILL.md"
echo "  /s2h https://github.com/user/repo/blob/main/SKILL.md"
echo ""
echo "Done."
