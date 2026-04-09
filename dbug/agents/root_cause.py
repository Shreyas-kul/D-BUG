"""Root Cause Agent — diagnoses why bugs occur using RAG + external data."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel

from dbug.agents.base import AgentBase
from dbug.mcp_client.tools import search_stackoverflow, search_web
from dbug.rag.retriever import HybridRetriever

logger = logging.getLogger(__name__)


class RootCause(BaseModel):
    """Diagnosed root cause of a bug."""

    bug_id: str
    title: str
    root_cause: str
    affected_file: str
    affected_lines: list[int]
    confidence: float  # 0.0 - 1.0
    category: str  # logic_error, type_error, boundary, null_ref, race_condition, security
    chain_of_thought: list[str]  # Step-by-step reasoning
    similar_bugs: list[str]  # Similar bugs found in knowledge base
    external_references: list[str]  # StackOverflow / GitHub links


class RootCauseResult(BaseModel):
    """Result of root cause analysis."""

    root_causes: list[RootCause]
    summary: str


class RootCauseAgent(AgentBase):
    """Diagnoses root causes using RAG context + web search."""

    name = "root_cause"
    system_prompt = (
        "You are a principal software engineer performing root cause analysis. "
        "Given a failing test or error, analyze the code thoroughly and determine "
        "the exact root cause. Use chain-of-thought reasoning:\n"
        "1. Understand what the code is supposed to do\n"
        "2. Identify what went wrong\n"
        "3. Trace the flow to the exact line(s) causing the issue\n"
        "4. Classify the bug type\n"
        "5. Explain why it happens\n"
        "Be precise. Point to exact lines and variables."
    )

    def __init__(self, retriever: Optional[HybridRetriever] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.retriever = retriever or HybridRetriever()

    async def run(
        self,
        error_message: str,
        code: str,
        file_path: str,
        test_code: str = "",
        **kwargs: Any,
    ) -> RootCauseResult:
        """Analyze a bug and determine root cause."""
        # Step 1: Retrieve similar code from vector DB
        rag_context = self.retriever.get_context_window(
            f"{error_message}\n{code[:500]}", max_tokens=2000
        )

        # Step 2: Search for similar bugs online (non-blocking, best-effort)
        external_refs = []
        try:
            so_result = await search_stackoverflow(error_message[:200])
            if so_result.success and so_result.data:
                external_refs.append(str(so_result.data)[:1000])
        except Exception:
            pass  # External search is optional

        # Step 3: Build analysis prompt
        prompt = (
            f"## Error / Failing Test\n{error_message}\n\n"
            f"## Code Under Analysis\nFile: {file_path}\n```\n{code}\n```\n\n"
        )
        if test_code:
            prompt += f"## Test Code\n```\n{test_code}\n```\n\n"
        if rag_context:
            prompt += f"## Related Code (from codebase)\n{rag_context}\n\n"
        if external_refs:
            prompt += f"## External References\n{external_refs[0]}\n\n"

        prompt += "Perform root cause analysis. Be specific about exact lines and variables."

        return await self.generate_structured(prompt, RootCauseResult)
