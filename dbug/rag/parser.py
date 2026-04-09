"""Tree-sitter based multi-language code parser."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Language extension mapping
LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
}


@dataclass
class ASTNode:
    """A node in the parsed AST."""

    type: str
    text: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    children: list[ASTNode]
    name: Optional[str] = None

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1


class CodeParser:
    """Multi-language code parser using tree-sitter."""

    def __init__(self) -> None:
        self._parsers: dict[str, Any] = {}
        self._languages: dict[str, Any] = {}

    def _get_parser(self, language: str) -> Any:
        """Lazily initialize parser for a language."""
        if language in self._parsers:
            return self._parsers[language]

        from tree_sitter import Language, Parser

        lang_module = self._load_language_module(language)
        if lang_module is None:
            raise ValueError(f"Unsupported language: {language}")

        lang = Language(lang_module.language())
        parser = Parser(lang)
        self._parsers[language] = parser
        self._languages[language] = lang
        return parser

    def _load_language_module(self, language: str) -> Any:
        """Dynamically import the tree-sitter language grammar."""
        module_map = {
            "python": "tree_sitter_python",
            "javascript": "tree_sitter_javascript",
        }
        module_name = module_map.get(language)
        if not module_name:
            return None

        try:
            import importlib

            return importlib.import_module(module_name)
        except ImportError:
            logger.warning(f"tree-sitter grammar not installed for {language}: pip install {module_name.replace('_', '-')}")
            return None

    def get_language(self, language: str) -> Any:
        """Get the Language object for queries."""
        if language not in self._languages:
            self._get_parser(language)
        return self._languages.get(language)

    def detect_language(self, file_path: Path) -> Optional[str]:
        """Detect language from file extension."""
        return LANGUAGE_MAP.get(file_path.suffix.lower())

    def parse(self, source: str | bytes, language: str) -> ASTNode:
        """Parse source code into an AST."""
        if isinstance(source, str):
            source = source.encode("utf-8")

        parser = self._get_parser(language)
        tree = parser.parse(source)
        return self._convert_node(tree.root_node, source)

    def parse_file(self, file_path: Path) -> Optional[ASTNode]:
        """Parse a file, auto-detecting language."""
        language = self.detect_language(file_path)
        if not language:
            return None

        try:
            source = file_path.read_bytes()
            return self.parse(source, language)
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None

    def _convert_node(self, node: Any, source: bytes) -> ASTNode:
        """Convert tree-sitter node to our ASTNode."""
        children = [self._convert_node(child, source) for child in node.children]

        name = None
        if node.type in ("function_definition", "class_definition", "method_definition"):
            for child in node.children:
                if child.type == "identifier" or child.type == "name":
                    name = source[child.start_byte : child.end_byte].decode("utf-8")
                    break

        return ASTNode(
            type=node.type,
            text=source[node.start_byte : node.end_byte].decode("utf-8", errors="replace"),
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            children=children,
            name=name,
        )

    @property
    def supported_languages(self) -> list[str]:
        """Return languages that have grammars installed."""
        supported = []
        for lang in ["python", "javascript"]:
            try:
                self._get_parser(lang)
                supported.append(lang)
            except (ValueError, ImportError):
                pass
        return supported
