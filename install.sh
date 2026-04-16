#!/bin/bash
# Nano Banana Studio -- DEPRECATED standalone installer
#
# As of v3.8.4, nano-banana-studio requires full plugin installation.
# The standalone skill-only install path is no longer supported because
# the plugin now includes two skills (banana + video), agents, and a
# .claude-plugin/ manifest that the skill runtime depends on.
#
# Install as a plugin instead:
#   claude plugin add juliandickie/nano-banana-studio

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo ""
echo -e "${RED}[DEPRECATED]${NC} Standalone skill installation is no longer supported as of v3.8.4."
echo ""
echo "Nano Banana Studio now requires full plugin installation."
echo "The plugin includes two skills (image + video), agents, and"
echo "configuration that only work in the plugin runtime."
echo ""
echo -e "${GREEN}Install as a plugin instead:${NC}"
echo ""
echo "  claude plugin add juliandickie/nano-banana-studio"
echo ""
echo "If you previously installed the standalone skill, remove it:"
echo ""
echo "  rm -rf ~/.claude/skills/banana"
echo ""
exit 1
