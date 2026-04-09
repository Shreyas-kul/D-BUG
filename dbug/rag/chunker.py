"""AST-aware code chunking — never splits mid-function."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dbug.rag.parser import ASTNode, CodeParser

logger = logging.getLogger(__name__)

# Node types we extract as chunks
CHUNK_NODE_TYPES = {
    "python": {"function_definition", "class_definition", "decorated_definition"},
    "javascript": {
        "function_declaration",
        "class_declaration",
        "arrow_function",
        "method_definition",
        "export_statement",
    },
}


@dataclass
class CodeChunk:
    """A semantically meaningful chunk of code."""

    id: str
    content: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    chunk_type: str  # function, class, module
    name: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    complexity: int = 0  # cyclomatic complexity estimate

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1

    def to_metadata(self) -> dict:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_type": self.chunk_type,
            "name": self.name or "",
            "complexity": self.complexity,
        }


class ASTChunker:
    """Chunks code using AST boundaries — never splits mid-function/class."""

    def __init__(self, max_chunk_lines: int = 100, parser: Optional[CodeParser] = None) -> None:
        self.max_chunk_lines = max_chunk_lines
        self.parser = parser or CodeParser()

    def chunk_file(self, file_path: Path) -> list[CodeChunk]:
        """Chunk a single file into semantic units."""
        language = self.parser.detect_language(file_path)
        if not language:
            return []

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Cannot read {file_path}: {e}")
            return []

        ast = self.parser.parse(source, language)
        if ast is None:
            return []

        chunks = self._extract_chunks(ast, str(file_path), language, source)

        # If no meaningful chunks found, treat whole file as one chunk
        if not chunks and source.strip():
            chunks = [
                CodeChunk(
                    id=self._make_id(str(file_path), 1, len(source.splitlines())),
                    content=source,
                    file_path=str(file_path),
                    language=language,
                    start_line=1,
                    end_line=len(source.splitlines()),
                    chunk_type="module",
                    name=file_path.stem,
                )
            ]

        return chunks

    def chunk_directory(self, directory: Path, exclude_dirs: Optional[set[str]] = None) -> list[CodeChunk]:
        """Chunk all supported files in a directory."""
        exclude = exclude_dirs or {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            "dist", "build", ".eggs", ".tox", "chroma_db",
        }
        chunks = []
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_dir():
                continue
            if any(part in exclude for part in file_path.parts):
                continue
            if self.parser.detect_language(file_path):
                chunks.extend(self.chunk_file(file_path))

        logger.info(f"Chunked {len(chunks)} code units from {directory}")
        return chunks

    def _extract_chunks(
        self, node: ASTNode, file_path: str, language: str, source: str
    ) -> list[CodeChunk]:
        """Recursively extract meaningful code chunks from AST."""
        chunks: list[CodeChunk] = []
        target_types = CHUNK_NODE_TYPES.get(language, set())

        for child in node.children:
            if child.type in target_types:
                chunk = CodeChunk(
                    id=self._make_id(file_path, child.start_line, child.end_line),
                    content=child.text,
                    file_path=file_path,
                    language=language,
                    start_line=child.start_line,
                    end_line=child.end_line,
                    chunk_type=self._classify_type(child.type),
                    name=child.name or self._extract_name(child),
                    complexity=self._estimate_complexity(child.text),
                    dependencies=self._extract_dependencies(child.text, language),
                )

                # If chunk is too large, extract sub-chunks
                if child.line_count > self.max_chunk_lines:
                    sub_chunks = self._extract_chunks(child, file_path, language, source)
                    if sub_chunks:
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(chunk)
                else:
                    chunks.append(chunk)
            else:
                # Recurse into non-target nodes
                chunks.extend(self._extract_chunks(child, file_path, language, source))

        return chunks

    @staticmethod
    def _classify_type(node_type: str) -> str:
        if "class" in node_type:
            return "class"
        if "function" in node_type or "method" in node_type or "arrow" in node_type:
            return "function"
        return "other"

    @staticmethod
    def _extract_name(node: ASTNode) -> Optional[str]:
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier"):
                return child.text
        return None

    @staticmethod
    def _estimate_complexity(code: str) -> int:
        """Rough cyclomatic complexity estimate via keyword counting."""
        keywords = ["if ", "elif ", "else:", "for ", "while ", "except ", "case ", "&&", "||", "? "]
        return 1 + sum(code.count(kw) for kw in keywords)

    @staticmethod
    def _extract_dependencies(code: str, language: str) -> list[str]:
        """Extract imported names and function calls."""
        deps = []
        for line in code.splitlines():
            stripped = line.strip()
            if language == "python":
                if stripped.startswith("import ") or stripped.startswith("from "):
                    deps.append(stripped)
            elif language == "javascript":
                if stripped.startswith("import ") or "require(" in stripped:
                    deps.append(stripped)
        return deps[:20]  # Cap dependencies

    @staticmethod
    def _make_id(file_path: str, start: int, end: int) -> str:
        raw = f"{file_path}:{start}-{end}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
