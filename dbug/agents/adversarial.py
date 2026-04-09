"""Adversarial Agent — generates edge-case tests designed to break code."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel

from dbug.agents.base import AgentBase

logger = logging.getLogger(__name__)


class AdversarialTest(BaseModel):
    """A generated adversarial test case."""

    test_name: str
    description: str
    test_code: str
    target_function: str
    target_file: str
    attack_category: str  # boundary, null_input, type_mismatch, injection, overflow, concurrency
    severity: str  # critical, high, medium, low
    expected_behavior: str


class AdversarialResult(BaseModel):
    """Result of adversarial test generation."""

    tests: list[AdversarialTest]
    target_file: str
    summary: str


class AdversarialAgent(AgentBase):
    """Generates edge-case tests designed to break code."""

    name = "adversarial"
    system_prompt = (
        "You are a world-class security researcher and QA engineer. Your job is to "
        "generate adversarial test cases that expose bugs, crashes, and vulnerabilities. "
        "Think like an attacker: what inputs would break this code? Focus on:\n"
        "- Boundary conditions (empty, max, min, off-by-one)\n"
        "- Null/None/undefined inputs\n"
        "- Type confusion and coercion\n"
        "- SQL injection, XSS, command injection\n"
        "- Integer overflow/underflow\n"
        "- Race conditions and concurrency\n"
        "- Resource exhaustion (very large inputs)\n"
        "- Unicode and special characters\n"
        "Generate executable test code using pytest (Python) or jest (JavaScript)."
    )

    async def run(
        self,
        code: str,
        file_path: str,
        language: str = "python",
        context: str = "",
        max_tests: int = 10,
        **kwargs: Any,
    ) -> AdversarialResult:
        """Generate adversarial tests for a code chunk."""
        prompt = (
            f"Generate {max_tests} adversarial test cases for this {language} code:\n\n"
            f"File: {file_path}\n"
            f"```{language}\n{code}\n```\n"
        )
        if context:
            prompt += f"\nAdditional context (related code):\n{context}\n"

        prompt += (
            f"\nGenerate exactly {max_tests} tests covering different attack categories. "
            f"Each test must be a complete, runnable test function."
        )

        return await self.generate_structured(prompt, AdversarialResult)

    async def generate_for_risk_area(
        self,
        risk_area: Any,
        source_code: str,
        context: str = "",
    ) -> AdversarialResult:
        """Generate tests specifically targeting a risk area."""
        prompt = (
            f"This code has been flagged as HIGH RISK:\n"
            f"Risk reasons: {getattr(risk_area, 'risk_reasons', [])}\n"
            f"Risk score: {getattr(risk_area, 'risk_score', 'unknown')}\n\n"
            f"File: {getattr(risk_area, 'file_path', '?')}\n"
            f"```\n{source_code}\n```\n\n"
            f"Generate adversarial tests specifically targeting the identified risks."
        )
        if context:
            prompt += f"\nRelated code:\n{context}\n"

        return await self.generate_structured(prompt, AdversarialResult)
