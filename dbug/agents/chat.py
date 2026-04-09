"""Interactive REPL — chat with D-BUG like Claude Code."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import warnings
from pathlib import Path
from typing import Any, Optional

# Suppress noisy warnings from libs
warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

logger = logging.getLogger(__name__)
console = Console()


# Intent classification — pure keyword matching, zero LLM tokens
INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("scan", ["scan", "find bugs", "check for bugs", "debug", "analyze bugs"]),
    ("health", ["health", "grade", "score", "rate", "quality"]),
    ("summary", ["summary", "summarize", "what does", "explain codebase", "describe project", "overview"]),
    ("test_gen", ["generate test", "adversarial test", "edge case test", "break this"]),
    ("read_file", ["read file", "show file", "open file", "cat ", "view file", "display file", "print file", "look at file"]),
    ("search", ["search", "google", "find online", "stackoverflow"]),
    ("fix", ["fix", "patch", "repair", "heal", "auto-fix"]),
    ("git", ["git ", "commit", "diff", "blame", "log", "history", "changes"]),
    ("help", ["help", "commands", "what can you do", "usage"]),
    ("exit", ["exit", "quit", "bye"]),
]


def _classify_intent(message: str) -> str:
    """Classify user intent from keywords — zero LLM cost."""
    msg = message.lower().strip()

    # Single char quit
    if msg in ("q", "exit", "quit", "bye"):
        return "exit"

    for intent, keywords in INTENT_PATTERNS:
        for kw in keywords:
            if kw in msg:
                return intent
    return "ask"  # Default: ask the LLM


def _extract_path(message: str) -> Optional[str]:
    """Extract a file/folder path from the message."""
    quoted = re.findall(r'["\']([^"\']+)["\']', message)
    if quoted:
        return quoted[0]
    words = message.split()
    for word in words:
        word = word.strip(".,!?")
        if "/" in word or ("." in word and len(word) > 2):
            p = Path(word)
            if p.exists() or p.suffix:
                return word
    return None


async def _handle_scan(message: str, cwd: str) -> str:
    from dbug.orchestrator.graph import DebugPipeline

    path = _extract_path(message) or cwd
    pipeline = DebugPipeline(on_progress=lambda m: console.print(f"  [dim]→ {m}[/dim]"))

    state = await pipeline.run(path, max_bugs=5)

    if not state.bugs:
        return f"✅ No bugs found in `{path}`!"

    lines = [f"🐛 **Found {state.bugs_found} bugs** ({state.bugs_fixed} auto-fixed):\n"]
    for i, bug in enumerate(state.bugs, 1):
        fixed = "✅" if bug.fix_validated else "❌"
        lines.append(f"{i}. **[{bug.severity.upper()}]** {bug.title} — `{Path(bug.file_path).name}:{bug.start_line}` {fixed}")
        if bug.root_cause:
            lines.append(f"   *Root cause:* {bug.root_cause[:80]}")
    return "\n".join(lines)


async def _handle_health(message: str, cwd: str) -> str:
    from dbug.agents.health_scorer import HealthScorer

    path = _extract_path(message) or cwd
    scorer = HealthScorer()
    report = scorer.score(Path(path))

    return (
        f"## Health: **{report.grade}** ({report.score:.0f}/100)\n\n"
        f"🔒 Security: {report.security_score:.0f} | "
        f"🧩 Complexity: {report.complexity_score:.0f} | "
        f"✨ Quality: {report.quality_score:.0f} | "
        f"📖 Docs: {report.documentation_score:.0f}\n\n"
        + "\n".join(f"- {r}" for r in report.top_recommendations[:3])
    )


async def _handle_summary(message: str, cwd: str) -> str:
    from dbug.agents.summarizer import Summarizer

    path = _extract_path(message) or cwd
    summarizer = Summarizer()
    return await summarizer.summarize(Path(path), use_ai=True)


async def _handle_test_gen(message: str, cwd: str) -> str:
    path = _extract_path(message)
    if not path or not Path(path).is_file():
        return "❌ Specify a file. Example: `generate tests for app.py`"

    from dbug.agents.adversarial import AdversarialAgent
    from dbug.rag.parser import CodeParser

    parser = CodeParser()
    target = Path(path)
    language = parser.detect_language(target)
    if not language:
        return f"❌ Unsupported file type: {target.suffix}"

    code = target.read_text()
    agent = AdversarialAgent()
    result = await agent.run(code=code, file_path=str(target), language=language, max_tests=3)

    lines = [f"⚔️ **{len(result.tests)} tests** for `{target.name}`:\n"]
    for t in result.tests:
        lines.append(f"### {t.test_name}\n```python\n{t.test_code}\n```\n")
    return "\n".join(lines)


async def _handle_read_file(message: str, cwd: str) -> str:
    path = _extract_path(message)
    if not path:
        return "❌ Specify a file. Example: `show file config.py`"

    target = Path(path)
    if not target.exists():
        target = Path(cwd) / path
    if not target.exists():
        return f"❌ File not found: `{path}`"

    content = target.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    if len(lines) > 50:
        content = "\n".join(lines[:50]) + f"\n\n... ({len(lines) - 50} more lines)"
    return f"📄 **{target.name}** ({len(lines)} lines):\n```\n{content}\n```"


async def _handle_search(message: str, cwd: str) -> str:
    from dbug.mcp_client.tools import search_web

    query = message.lower()
    for word in ["search", "google", "find", "look up", "search for"]:
        query = query.replace(word, "")
    query = query.strip()

    if not query:
        return "❌ Example: `search python async best practices`"

    result = await search_web(query, max_results=3)
    if result.success:
        return f"🔍 **{query}**\n\n{result.data}"
    return f"❌ Search failed: {result.error}"


async def _handle_git(message: str, cwd: str) -> str:
    msg = message.lower()
    try:
        if "log" in msg or "history" in msg:
            out = subprocess.run(["git", "log", "--oneline", "-10"], capture_output=True, text=True, cwd=cwd)
            return f"📜 **Recent commits:**\n```\n{out.stdout}\n```"
        elif "diff" in msg:
            out = subprocess.run(["git", "diff", "--stat"], capture_output=True, text=True, cwd=cwd)
            return f"📝 **Git diff:**\n```\n{out.stdout or 'No changes'}\n```"
        elif "blame" in msg:
            path = _extract_path(message)
            if not path:
                return "❌ Specify a file. Example: `git blame config.py`"
            out = subprocess.run(["git", "blame", path, "--date=short"], capture_output=True, text=True, cwd=cwd)
            lines = out.stdout.splitlines()[:20]
            return f"👤 **Git blame** `{path}`:\n```\n" + "\n".join(lines) + "\n```"
        else:
            out = subprocess.run(["git", "status", "-s"], capture_output=True, text=True, cwd=cwd)
            return f"📊 **Git status:**\n```\n{out.stdout or 'Clean working tree'}\n```"
    except Exception as e:
        return f"❌ Git error: {e}"


async def _handle_ask(message: str, cwd: str) -> str:
    """Free-form question — fast LLM answer, skip RAG for speed."""
    from dbug.llm import get_llm

    llm = get_llm()
    response = await llm.generate(
        prompt=message,
        system="You are D-BUG, an AI debugging assistant. Answer concisely in 2-3 sentences max.",
        max_tokens=200,
    )
    return response.content


HELP_TEXT = """
## 🐛 D-BUG Commands

| Say this | What happens |
|---|---|
| `scan .` | AI bug scan |
| `health` | A-F health grade |
| `summary` | Codebase overview |
| `generate tests for app.py` | Edge-case tests |
| `show file config.py` | View a file |
| `search python async tips` | Web search |
| `git log` / `git diff` | Git operations |
| `fix .` | Auto-fix bugs |
| *Any question* | AI answers it |
| `q` | Quit |
"""


HANDLERS = {
    "scan": _handle_scan,
    "health": _handle_health,
    "summary": _handle_summary,
    "test_gen": _handle_test_gen,
    "read_file": _handle_read_file,
    "search": _handle_search,
    "fix": _handle_scan,
    "git": _handle_git,
    "ask": _handle_ask,
}


async def chat_loop(cwd: str = ".") -> None:
    """Main interactive REPL loop."""
    console.print(Panel(
        "[bold cyan]🐛 D-BUG Interactive Mode[/bold cyan]\n"
        "[dim]Type anything. 'help' for commands, 'q' to quit.[/dim]",
        border_style="cyan",
    ))
    console.print()

    while True:
        try:
            user_input = console.input("[bold cyan]dbug>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye! 🐛[/dim]")
            break

        if not user_input:
            continue

        intent = _classify_intent(user_input)

        if intent == "exit":
            console.print("[dim]Goodbye! 🐛[/dim]")
            break

        if intent == "help":
            console.print(Markdown(HELP_TEXT))
            continue

        handler = HANDLERS.get(intent, _handle_ask)
        try:
            result = await handler(user_input, cwd)
            console.print()
            console.print(Markdown(result))
            console.print()
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}\n")
