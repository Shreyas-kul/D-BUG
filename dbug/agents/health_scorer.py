"""Code Health Score — A-F grading for any codebase."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dbug.rag.chunker import ASTChunker, CodeChunk

logger = logging.getLogger(__name__)


@dataclass
class HealthReport:
    """Overall health report for a codebase."""

    grade: str  # A, B, C, D, F
    score: float  # 0-100
    total_files: int
    total_functions: int
    total_lines: int
    languages: list[str]

    # Breakdown
    security_score: float
    complexity_score: float
    quality_score: float
    documentation_score: float

    # Issues
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int

    # Recommendations
    top_recommendations: list[str]

    @property
    def badge_color(self) -> str:
        return {"A": "brightgreen", "B": "green", "C": "yellow", "D": "orange", "F": "red"}.get(
            self.grade, "gray"
        )

    def to_badge_url(self) -> str:
        return f"https://img.shields.io/badge/D--BUG_Health-{self.grade}_{self.score:.0f}%25-{self.badge_color}"


class HealthScorer:
    """Calculate a health score for any codebase."""

    def __init__(self, chunker: Optional[ASTChunker] = None) -> None:
        self.chunker = chunker or ASTChunker()

    def score(self, path: Path) -> HealthReport:
        """Score a codebase from 0-100 with an A-F grade."""
        chunks = self.chunker.chunk_directory(path)
        if not chunks:
            return HealthReport(
                grade="?", score=0, total_files=0, total_functions=0, total_lines=0,
                languages=[], security_score=0, complexity_score=0, quality_score=0,
                documentation_score=0, critical_issues=0, high_issues=0,
                medium_issues=0, low_issues=0, top_recommendations=["No code found"],
            )

        # Analyze
        security = self._score_security(chunks)
        complexity = self._score_complexity(chunks)
        quality = self._score_quality(chunks)
        documentation = self._score_documentation(chunks)

        # Weighted average
        score = (security * 0.35 + complexity * 0.25 + quality * 0.25 + documentation * 0.15)

        # Count issues
        issues = self._count_issues(chunks)
        grade = self._score_to_grade(score)

        return HealthReport(
            grade=grade,
            score=round(score, 1),
            total_files=len({c.file_path for c in chunks}),
            total_functions=len(chunks),
            total_lines=sum(c.line_count for c in chunks),
            languages=list({c.language for c in chunks}),
            security_score=round(security, 1),
            complexity_score=round(complexity, 1),
            quality_score=round(quality, 1),
            documentation_score=round(documentation, 1),
            critical_issues=issues["critical"],
            high_issues=issues["high"],
            medium_issues=issues["medium"],
            low_issues=issues["low"],
            top_recommendations=self._get_recommendations(chunks, security, complexity, quality),
        )

    def _score_security(self, chunks: list[CodeChunk]) -> float:
        """0-100 security score. Higher = safer."""
        total = len(chunks)
        if total == 0:
            return 100

        vulns = 0
        dangerous = [
            "eval(", "exec(", "os.system(", "pickle.load", "yaml.load(",
            "innerHTML", "f\"select", "f'select", "__import__(",
            "shell=True", "password =", "secret =", "api_key =",
        ]
        for chunk in chunks:
            content = chunk.content.lower()
            for pattern in dangerous:
                if pattern in content:
                    vulns += 1
                    break

        return max(0, 100 - (vulns / total * 200))

    def _score_complexity(self, chunks: list[CodeChunk]) -> float:
        """0-100. Lower complexity = higher score."""
        if not chunks:
            return 100
        avg_complexity = sum(c.complexity for c in chunks) / len(chunks)
        avg_length = sum(c.line_count for c in chunks) / len(chunks)

        # Ideal: complexity < 5, length < 30
        complexity_penalty = max(0, (avg_complexity - 5) * 8)
        length_penalty = max(0, (avg_length - 30) * 2)

        return max(0, 100 - complexity_penalty - length_penalty)

    def _score_quality(self, chunks: list[CodeChunk]) -> float:
        """0-100 code quality."""
        if not chunks:
            return 100
        issues = 0
        for chunk in chunks:
            content = chunk.content.lower()
            if "except:" in content or "except Exception:" in content:
                issues += 1
            if "# todo" in content or "# fixme" in content or "# hack" in content:
                issues += 1
            if "print(" in content and chunk.chunk_type == "function":
                issues += 0.5  # Debug prints left in
            if "pass" in content and "except" in content:
                issues += 1  # Silent error swallowing

        return max(0, 100 - (issues / len(chunks) * 50))

    def _score_documentation(self, chunks: list[CodeChunk]) -> float:
        """0-100 documentation coverage."""
        if not chunks:
            return 100
        documented = sum(1 for c in chunks if '"""' in c.content or "'''" in c.content or "/**" in c.content)
        return (documented / len(chunks)) * 100

    def _count_issues(self, chunks: list[CodeChunk]) -> dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        critical_patterns = ["eval(", "exec(", "os.system(", "pickle.load", "f\"select", "f'select"]
        high_patterns = ["except:", "shell=True", "innerHTML", "password ="]
        medium_patterns = ["# todo", "# fixme", "# hack", "except Exception:"]

        for chunk in chunks:
            content = chunk.content.lower()
            if any(p in content for p in critical_patterns):
                counts["critical"] += 1
            elif any(p in content for p in high_patterns):
                counts["high"] += 1
            elif any(p in content for p in medium_patterns):
                counts["medium"] += 1

        return counts

    def _get_recommendations(self, chunks: list, sec: float, comp: float, qual: float) -> list[str]:
        recs = []
        if sec < 60:
            recs.append("🔴 CRITICAL: Remove eval(), os.system(), and SQL string formatting")
        if sec < 80:
            recs.append("🟡 Use parameterized queries instead of f-strings for SQL")
        if comp < 60:
            recs.append("🟡 Refactor complex functions (break into smaller units)")
        if qual < 60:
            recs.append("🟡 Replace bare except with specific exception types")
        if not recs:
            recs.append("🟢 Looking good! Keep up the code quality.")
        return recs[:5]

    @staticmethod
    def _score_to_grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 65:
            return "C"
        if score >= 50:
            return "D"
        return "F"
