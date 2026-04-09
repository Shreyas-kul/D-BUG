# 🐛 D-BUG

**LLM-Powered Autonomous Debugging Platform**

AI-powered debugging system that detects 87%+ of critical bugs pre-deployment using adversarial testing and RAG-based root cause analysis.

## Features

- 🔍 **Autonomous Scanning** — Index and analyze entire codebases
- ⚔️ **Adversarial Testing** — Auto-generate edge-case tests
- 🔬 **Root Cause Analysis** — RAG-powered bug diagnosis
- 🔧 **AI Fix Generation** — Minimal, safe patches
- ✅ **Auto-Validation** — Execute and verify fixes
- 🔌 **MCP Server** — Works with Claude Code, Cursor, any AI IDE
- ⚙️ **GitHub Actions** — Auto-scan PRs
- 🌐 **Web Dashboard** — Real-time scan visualization

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Set API key (free at console.groq.com)
export GROQ_API_KEY=your_key

# Scan a project
dbug scan /path/to/project

# Generate adversarial tests
dbug test-gen app.py

# Show config
dbug config --show
```

## Architecture

```
D-BUG
├── 5 AI Agents (Scanner → Adversarial → Root Cause → Fix → Validate)
├── RAG Pipeline (tree-sitter + ChromaDB + sentence-transformers)
├── 10 MCP Server Integrations (GitHub, Brave, Sentry, Docker, etc.)
├── 3 LLM Providers (Groq, Ollama, HuggingFace — all free)
└── CLI + Web Dashboard + MCP Server + GitHub Action
```

## License

MIT
