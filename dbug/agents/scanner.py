"""Scanner Agent — indexes codebase and identifies high-risk areas."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from dbug.agents.base import AgentBase
from dbug.rag.chunker import ASTChunker, CodeChunk
from dbug.rag.retriever import HybridRetriever

logger = logging.getLogger(__name__)


class RiskArea(BaseModel):
    """A high-risk code area identified by the scanner."""

    file_path: str
    function_name: str
    start_line: int
    end_line: int
    risk_score: float  # 0.0 - 1.0
    risk_reasons: list[str]
    category: str  # "complexity", "no_tests", "recent_changes", "security"


class ScanResult(BaseModel):
    """Result of scanning a codebase."""

    total_files: int
    total_chunks: int
    total_lines: int
    languages: list[str]
    high_risk_areas: list[RiskArea]
    summary: str


class ScannerAgent(AgentBase):
    """Indexes the codebase and identifies high-risk areas."""

    name = "scanner"
    system_prompt = (
        "You are an expert code reviewer. Analyze code chunks and identify areas "
        "that are most likely to contain bugs. Focus on: high complexity, missing error "
        "handling, unsafe operations, untested code paths, and recent changes."
    )

    def __init__(self, retriever: Optional[HybridRetriever] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.retriever = retriever or HybridRetriever()

    async def run(
        self,
        path: Path,
        max_risk_areas: int = 20,
        **kwargs: Any,
    ) -> ScanResult:
        """Scan a codebase and return risk analysis."""
        path = Path(path)
        logger.info(f"Scanning codebase: {path}")

        # Step 1: Index codebase
        chunker = self.retriever.chunker
        chunks = chunker.chunk_directory(path)
        indexed = self.retriever.vectorstore.index_chunks(chunks)
        logger.info(f"Indexed {indexed} chunks")

        # Step 2: Identify high-risk areas via heuristics
        risk_candidates = self._heuristic_risk_analysis(chunks)

        # Step 3: LLM-powered deep analysis on top candidates
        high_risk_areas = []
        for chunk in risk_candidates[:max_risk_areas]:
            try:
                risk = await self._analyze_chunk(chunk)
                if risk and risk.risk_score >= 0.4:
                    high_risk_areas.append(risk)
            except Exception as e:
                logger.warning(f"Failed to analyze {chunk.file_path}:{chunk.start_line}: {e}")

        # Sort by risk score
        high_risk_areas.sort(key=lambda r: r.risk_score, reverse=True)

        languages = list({c.language for c in chunks})
        total_lines = sum(c.line_count for c in chunks)

        return ScanResult(
            total_files=len({c.file_path for c in chunks}),
            total_chunks=len(chunks),
            total_lines=total_lines,
            languages=languages,
            high_risk_areas=high_risk_areas[:max_risk_areas],
            summary=f"Scanned {len(chunks)} code units across {len(languages)} languages. "
            f"Found {len(high_risk_areas)} high-risk areas.",
        )

    def _heuristic_risk_analysis(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Pre-filter chunks by heuristic risk signals."""
        scored: list[tuple[float, CodeChunk]] = []

        for chunk in chunks:
            score = 0.0

            # Complexity
            if chunk.complexity > 10:
                score += 0.3
            elif chunk.complexity > 5:
                score += 0.15

            # Long functions are risky
            if chunk.line_count > 50:
                score += 0.2
            elif chunk.line_count > 30:
                score += 0.1

            # Check for risky patterns
            content_lower = chunk.content.lower()
            risk_patterns = [
                ("eval(", 0.3),
                ("exec(", 0.3),
                ("subprocess", 0.2),
                ("os.system", 0.25),
                ("sql", 0.15),
                ("password", 0.15),
                ("secret", 0.15),
                ("todo", 0.1),
                ("fixme", 0.15),
                ("hack", 0.15),
                ("# type: ignore", 0.1),
                ("noqa", 0.1),
                ("except:", 0.15),  # Bare except
                ("except Exception:", 0.1),
            ]
            for pattern, weight in risk_patterns:
                if pattern in content_lower:
                    score += weight

            if score > 0.1:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored]

    async def _analyze_chunk(self, chunk: CodeChunk) -> Optional[RiskArea]:
        """Use LLM to analyze a code chunk for risks."""
        prompt = (
            f"Analyze this {chunk.language} code for potential bugs and risks:\n\n"
            f"File: {chunk.file_path}\n"
            f"Lines: {chunk.start_line}-{chunk.end_line}\n"
            f"```{chunk.language}\n{chunk.content}\n```\n\n"
            f"Rate the risk from 0.0 (safe) to 1.0 (critical bug likely)."
        )
        return await self.generate_structured(prompt, RiskArea)
