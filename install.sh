#!/usr/bin/env bash
# D-BUG One-Command Installer
# Usage: curl -sL <repo>/install.sh | bash
# Or:    bash install.sh

set -e

echo "🐛 Installing D-BUG..."

# Check Python
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "❌ Python not found. Install Python 3.9+ first."
    exit 1
fi

VERSION=$($PY -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$($PY -c "import sys; print(sys.version_info.major)")
MINOR=$($PY -c "import sys; print(sys.version_info.minor)")

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 9 ]); then
    echo "❌ Python $VERSION found, but D-BUG needs 3.9+."
    exit 1
fi

echo "✅ Python $VERSION found"

# Install D-BUG
$PY -m pip install . --quiet

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  🐛 D-BUG installed successfully!    ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Run these commands:"
echo "  dbug chat         # Interactive AI assistant"
echo "  dbug scan .       # Scan for bugs"
echo "  dbug health .     # Health grade"
echo "  dbug --help       # All commands"
echo ""
echo "⚠️  Set your API key first:"
echo "  export GROQ_API_KEY=your-key-here"
echo ""
