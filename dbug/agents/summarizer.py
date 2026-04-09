"""Codebase summarizer — 95% heuristic, 5% AI. Ultra token-efficient."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from dbug.rag.chunker import ASTChunker, CodeChunk

logger = logging.getLogger(__name__)


class CodebaseSummary:
    """Structured summary built from pure heuristics."""

    def __init__(self) -> None:
        self.total_files: int = 0
        self.total_lines: int = 0
        self.languages: Counter = Counter()
        self.functions: list[str] = []
        self.classes: list[str] = []
        self.imports: Counter = Counter()
        self.entry_points: list[str] = []
        self.frameworks: list[str] = []
        self.file_tree: list[str] = []

    def to_compact(self) -> str:
        """Compress everything into ~300 tokens for LLM."""
        parts = [
            f"Files:{self.total_files} Lines:{self.total_lines}",
            f"Langs:{dict(self.languages.most_common(5))}",
            f"Top imports:{dict(self.imports.most_common(10))}",
            f"Classes:{self.classes[:15]}",
            f"Functions:{self.functions[:20]}",
            f"Frameworks:{self.frameworks}",
            f"Entry:{self.entry_points[:5]}",
        ]
        return "\n".join(parts)


class Summarizer:
    """Summarize any codebase. Heuristic-first, AI only for final paragraph."""

    FRAMEWORK_SIGNALS = {
        "fastapi": ["fastapi", "APIRouter", "Depends"],
        "flask": ["flask", "Flask", "Blueprint"],
        "django": ["django", "models.Model", "views"],
        "react": ["react", "useState", "useEffect", "jsx"],
        "express": ["express", "app.get", "app.post", "router"],
        "pytorch": ["torch", "nn.Module", "tensor"],
        "langchain": ["langchain", "LLMChain", "PromptTemplate"],
        "typer": ["typer", "typer.Typer"],
        "pydantic": ["pydantic", "BaseModel", "Field"],
    }

    def __init__(self, chunker: Optional[ASTChunker] = None) -> None:
        self.chunker = chunker or ASTChunker()

    def analyze(self, path: Path) -> CodebaseSummary:
        """Pure heuristic analysis — zero AI, instant."""
        summary = CodebaseSummary()
        path = Path(path).resolve()

        # Collect all source files
        exclude = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", "chroma_db"}
        source_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c"}
        all_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c",
                    ".html", ".css", ".json", ".toml", ".yaml", ".yml", ".md", ".sql", ".sh"}

        files: list[Path] = []
        for f in sorted(path.rglob("*")):
            if f.is_file() and not any(p in exclude for p in f.parts):
                if f.suffix in all_exts:
                    files.append(f)

        summary.total_files = len(files)

        # Build file tree (compact)
        for f in files[:50]:
            rel = f.relative_to(path)
            summary.file_tree.append(str(rel))

        # Analyze source files
        for f in files:
            if f.suffix not in source_exts:
                continue

            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()
            summary.total_lines += len(lines)
            summary.languages[f.suffix] += 1

            # Extract imports
            for line in lines:
                stripped = line.strip()
                if f.suffix == ".py":
                    if stripped.startswith("import "):
                        mod = stripped.split()[1].split(".")[0]
                        summary.imports[mod] += 1
                    elif stripped.startswith("from "):
                        mod = stripped.split()[1].split(".")[0]
                        summary.imports[mod] += 1
                elif f.suffix in (".js", ".ts", ".jsx", ".tsx"):
                    if "import " in stripped and "from" in stripped:
                        parts = stripped.split("from")
                        if len(parts) > 1:
                            mod = parts[-1].strip().strip("'\"; ")
                            summary.imports[mod.split("/")[0]] += 1

            # Detect frameworks
            content_lower = content.lower()
            for framework, signals in self.FRAMEWORK_SIGNALS.items():
                if any(sig.lower() in content_lower for sig in signals):
                    if framework not in summary.frameworks:
                        summary.frameworks.append(framework)

            # Detect entry points
            if "if __name__" in content or "app.listen" in content or "def main" in content:
                summary.entry_points.append(str(f.relative_to(path)))

        # AST-level analysis for source files
        chunks = self.chunker.chunk_directory(path)
        for chunk in chunks:
            if chunk.chunk_type == "class" and chunk.name:
                summary.classes.append(chunk.name)
            elif chunk.chunk_type == "function" and chunk.name:
                summary.functions.append(chunk.name)

        return summary

    async def summarize(self, path: Path, use_ai: bool = True) -> str:
        """Get a full summary. Heuristic first, optional AI polish."""
        summary = self.analyze(path)

        # Build heuristic summary (always works, no AI)
        lang_str = ", ".join(f"{ext}({c})" for ext, c in summary.languages.most_common(5))
        top_imports = ", ".join(f"{m}" for m, _ in summary.imports.most_common(8))

        heuristic = (
            f"📁 {summary.total_files} files | {summary.total_lines:,} lines | {lang_str}\n"
            f"🏗️  Frameworks: {', '.join(summary.frameworks) or 'none detected'}\n"
            f"📦 Top deps: {top_imports}\n"
            f"🧩 {len(summary.classes)} classes, {len(summary.functions)} functions\n"
            f"🚀 Entry points: {', '.join(summary.entry_points[:3]) or 'none detected'}\n"
        )

        if summary.classes:
            heuristic += f"📋 Classes: {', '.join(summary.classes[:10])}\n"
        if summary.functions:
            heuristic += f"📋 Key functions: {', '.join(summary.functions[:12])}\n"

        if not use_ai:
            return heuristic

        # AI polish — single call, ~300 input tokens, ~150 output tokens
        try:
            from dbug.llm import get_llm

            llm = get_llm()
            compact = summary.to_compact()
            response = await llm.generate(
                prompt=(
                    f"Codebase stats:\n{compact}\n\n"
                    "Write a 2-3 sentence project summary. What does this project do? Be specific."
                ),
                system="Summarize codebases in 2-3 sentences. Be specific about purpose and tech.",
                max_tokens=150,
            )
            return heuristic + f"\n🤖 AI Summary: {response.content.strip()}"
        except Exception as e:
            logger.warning(f"AI summary failed: {e}")
            return heuristic
