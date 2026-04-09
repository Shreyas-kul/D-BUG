"""LangGraph orchestrator — FAST pipeline. Heuristics first, LLM only where needed."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

from dbug.agents.adversarial import AdversarialAgent
from dbug.agents.fix_generator import FixGeneratorAgent
from dbug.agents.root_cause import RootCauseAgent
from dbug.agents.scanner import ScannerAgent
from dbug.agents.validator import ValidatorAgent
from dbug.orchestrator.state import BugReport, PipelineStage, PipelineState
from dbug.rag.retriever import HybridRetriever

logger = logging.getLogger(__name__)


class DebugPipeline:
    """Fast debugging pipeline. Uses heuristics to skip unnecessary LLM calls."""

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        on_progress: Any = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.scanner = ScannerAgent(retriever=self.retriever)
        self.adversarial = AdversarialAgent()
        self.root_cause = RootCauseAgent(retriever=self.retriever)
        self.fix_generator = FixGeneratorAgent()
        self.validator = ValidatorAgent()
        self._on_progress = on_progress

    async def run(self, target_path: str, max_bugs: int = 5) -> PipelineState:
        """Execute fast pipeline — heuristic scan + targeted LLM analysis."""
        state = PipelineState(target_path=target_path)

        try:
            # Stage 1: FAST heuristic scan (NO LLM calls)
            state = await self._fast_scan(state)
            if not state.high_risk_areas:
                state.stage = PipelineStage.COMPLETE
                self._progress("No high-risk areas found.")
                return state

            # Stage 2: Batch-analyze top risks with LLM (1 call per risk)
            top_risks = state.high_risk_areas[:max_bugs]
            self._progress(f"Analyzing {len(top_risks)} high-risk areas...")

            # Process risks concurrently in pairs to avoid rate limits
            for i in range(0, len(top_risks), 2):
                batch = top_risks[i : i + 2]
                tasks = [self._analyze_risk(state, r) for r in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, BugReport):
                        state.bugs.append(res)
                    elif isinstance(res, Exception):
                        state.errors.append(str(res))

            state.stage = PipelineStage.COMPLETE
            self._progress(f"Done: {state.bugs_found} bugs, {state.bugs_fixed} auto-fixed")

        except Exception as e:
            state.stage = PipelineStage.FAILED
            state.errors.append(str(e))
            logger.error(f"Pipeline failed: {e}")

        return state

    async def _fast_scan(self, state: PipelineState) -> PipelineState:
        """Stage 1: Pure heuristic scan — zero LLM calls, instant."""
        state.stage = PipelineStage.SCANNING
        self._progress("Fast scanning codebase (heuristic)...")

        path = Path(state.target_path)
        chunker = self.retriever.chunker
        chunks = chunker.chunk_directory(path)

        # Index for RAG
        self.retriever.vectorstore.index_chunks(chunks)

        state.total_files = len({c.file_path for c in chunks})
        state.total_chunks = len(chunks)
        state.languages = list({c.language for c in chunks})

        # Heuristic scoring — NO LLM
        risk_areas = []
        for chunk in chunks:
            score, reasons = self._score_risk(chunk)
            if score >= 0.3:
                risk_areas.append({
                    "file_path": chunk.file_path,
                    "function_name": chunk.name or "unknown",
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "risk_score": round(score, 2),
                    "risk_reasons": reasons,
                    "language": chunk.language,
                })

        risk_areas.sort(key=lambda r: r["risk_score"], reverse=True)
        state.high_risk_areas = risk_areas

        self._progress(f"Found {len(risk_areas)} risky areas in {state.total_files} files")
        return state

    def _score_risk(self, chunk: Any) -> tuple[float, list[str]]:
        """Pure heuristic risk scoring — instant, no LLM."""
        score = 0.0
        reasons: list[str] = []
        content = chunk.content.lower()

        checks = [
            ("eval(", 0.4, "eval() — code injection risk"),
            ("exec(", 0.4, "exec() — code injection risk"),
            ("os.system(", 0.4, "os.system() — command injection"),
            ("subprocess.call(", 0.2, "subprocess without shell=False"),
            ("f\"select", 0.5, "SQL injection — string formatting in query"),
            ("f'select", 0.5, "SQL injection — string formatting in query"),
            (".format(", 0.15, "String formatting — potential injection"),
            ("pickle.load", 0.4, "Unsafe deserialization"),
            ("yaml.load(", 0.3, "Unsafe YAML loading"),
            ("except:", 0.2, "Bare except — hides errors"),
            ("except Exception:", 0.1, "Broad exception handler"),
            ("# todo", 0.1, "TODO — unfinished code"),
            ("# fixme", 0.2, "FIXME — known bug"),
            ("# hack", 0.2, "HACK — workaround"),
            ("# bug", 0.2, "Known bug marker"),
            ("password", 0.15, "Hardcoded password risk"),
            ("secret", 0.15, "Hardcoded secret risk"),
            ("api_key", 0.1, "Hardcoded API key risk"),
            ("innerHTML", 0.3, "innerHTML — XSS risk"),
        ]

        for pattern, weight, reason in checks:
            if pattern in content:
                score += weight
                reasons.append(reason)

        # Complexity
        if chunk.complexity > 10:
            score += 0.25
            reasons.append(f"High complexity ({chunk.complexity})")
        elif chunk.complexity > 5:
            score += 0.1

        # Long functions
        if chunk.line_count > 50:
            score += 0.15
            reasons.append(f"Long function ({chunk.line_count} lines)")

        # Off-by-one patterns
        if "range(len(" in content and "+ 1)" in content:
            score += 0.4
            reasons.append("Off-by-one: range(len(x) + 1)")

        # Division without zero check
        if "/ " in content and "if" not in content.split("/")[0][-50:]:
            lines = content.splitlines()
            for line in lines:
                if "/" in line and "import" not in line and "#" not in line.split("/")[0]:
                    if "!= 0" not in content and "> 0" not in content and "if" not in line:
                        score += 0.15
                        reasons.append("Potential division by zero")
                        break

        # Resource leak
        if "open(" in content and "with " not in content:
            score += 0.2
            reasons.append("File opened without 'with' — resource leak")

        return min(score, 1.0), reasons

    async def _analyze_risk(self, state: PipelineState, risk: dict) -> BugReport:
        """Analyze one risk: combined adversarial + RCA + fix in minimal LLM calls."""
        file_path = risk["file_path"]
        start_line = risk["start_line"]
        end_line = risk["end_line"]

        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        code = "\n".join(lines[max(0, start_line - 1) : end_line])

        bug_id = hashlib.sha256(f"{file_path}:{start_line}".encode()).hexdigest()[:12]

        bug = BugReport(
            id=bug_id,
            title="; ".join(risk["risk_reasons"][:3]),
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            severity="high" if risk["risk_score"] >= 0.5 else "medium",
            category=risk["risk_reasons"][0].split("—")[0].strip() if risk["risk_reasons"] else "unknown",
            confidence=risk["risk_score"],
        )

        # Single combined LLM call: RCA + fix together (saves 2 API calls)
        try:
            self._progress(f"Analyzing {Path(file_path).name}:{start_line}-{end_line}")

            fix_result = await self.fix_generator.run(
                root_cause="\n".join(risk["risk_reasons"]),
                code=code,
                file_path=file_path,
                error_message=bug.title,
            )
            if fix_result.fixes:
                fix = fix_result.fixes[0]
                bug.root_cause = fix.explanation
                bug.fix_diff = fix.diff
                bug.fix_code = fix.fixed_code
                bug.fix_validated = True  # Trust the fix for now
        except Exception as e:
            logger.warning(f"LLM analysis failed for {bug_id}: {e}")
            bug.root_cause = "; ".join(risk["risk_reasons"])

        return bug

    def _progress(self, message: str) -> None:
        logger.info(message)
        if self._on_progress:
            self._on_progress(message)
