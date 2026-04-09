"""Fix Generator Agent — lean prompts, fast responses."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from dbug.agents.base import AgentBase

logger = logging.getLogger(__name__)


class CodeFix(BaseModel):
    bug_id: str = ""
    file_path: str
    original_code: str
    fixed_code: str
    diff: str
    explanation: str
    breaking_changes: list[str] = []
    confidence: float = 0.8


class FixResult(BaseModel):
    fixes: list[CodeFix]
    summary: str


class FixGeneratorAgent(AgentBase):
    name = "fix_generator"
    system_prompt = (
        "You fix bugs. Be concise. Output JSON only.\n"
        "Rules: minimal changes, preserve behavior, add error handling."
    )

    async def run(
        self,
        root_cause: str,
        code: str,
        file_path: str,
        error_message: str = "",
        context: str = "",
        **kwargs: Any,
    ) -> FixResult:
        # Truncate code to save tokens
        code = code[:2000]
        prompt = (
            f"Bugs: {root_cause[:500]}\n"
            f"File: {file_path}\n```\n{code}\n```\n"
            f"Generate fix with original_code, fixed_code, diff, explanation."
        )
        return await self.generate_structured(prompt, FixResult, max_tokens=1500)
