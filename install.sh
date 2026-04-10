#!/usr/bin/env bash
# ╔══════════════════════════════════════╗
# ║  🐛 D-BUG Installer                  ║
# ║  One command. Any Python. Any OS.     ║
# ╚══════════════════════════════════════╝
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}🐛 Installing D-BUG...${NC}"
echo ""

# Find Python (try python3 first, then python)
PY=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$($cmd -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>/dev/null)
        MAJOR=$($cmd -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        MINOR=$($cmd -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ] 2>/dev/null; then
            PY="$cmd"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    echo -e "${RED}❌ Python 3.9+ not found.${NC}"
    echo ""
    echo "Install Python from: https://www.python.org/downloads/"
    echo "  macOS:   brew install python3"
    echo "  Ubuntu:  sudo apt install python3 python3-pip"
    echo "  Windows: winget install Python.Python.3.12"
    exit 1
fi

echo -e "  ${GREEN}✅${NC} Found $PY ($VER)"

# Install D-BUG
echo -e "  ${CYAN}→${NC} Installing dependencies..."
$PY -m pip install . --quiet --break-system-packages 2>/dev/null || $PY -m pip install . --quiet

# Verify
if command -v dbug &>/dev/null; then
    echo ""
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║  🐛 D-BUG installed successfully!    ║${NC}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}Get started:${NC}"
    echo -e "    ${CYAN}dbug chat${NC}         Interactive AI assistant"
    echo -e "    ${CYAN}dbug scan .${NC}       Scan for bugs"
    echo -e "    ${CYAN}dbug health .${NC}     Health grade (A-F)"
    echo -e "    ${CYAN}dbug --help${NC}       All commands"
    echo ""
    echo -e "  ${BOLD}⚠️  Set your API key first (free):${NC}"
    echo -e "    export GROQ_API_KEY=your-key-from-console.groq.com"
    echo ""
else
    # dbug not on PATH — tell user how to fix
    SCRIPTS=$($PY -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null)
    echo ""
    echo -e "${GREEN}✅ D-BUG installed!${NC} But 'dbug' isn't on your PATH yet."
    echo ""
    echo "Add this to your shell profile (~/.bashrc or ~/.zshrc):"
    echo "  export PATH=\"$SCRIPTS:\$PATH\""
    echo ""
    echo "Then restart your terminal and run: dbug chat"
fi
