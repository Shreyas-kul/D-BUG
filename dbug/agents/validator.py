"""Validator Agent — validates fixes by running tests and checking for regressions."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from dbug.agents.base import AgentBase

logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Result of validating a fix."""

    passed: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    regression_detected: bool
    output: str
    recommendations: list[str]


class ValidatorAgent(AgentBase):
    """Validates fixes by executing tests and checking for regressions."""

    name = "validator"
    system_prompt = (
        "You are a QA validation engineer. Analyze test results and determine "
        "if a fix is safe to apply. Check for:\n"
        "1. All original tests still pass\n"
        "2. The new adversarial test now passes\n"
        "3. No new regressions introduced\n"
        "4. Edge cases are handled properly"
    )

    async def run(
        self,
        original_code: str,
        fixed_code: str,
        test_code: str,
        file_path: str,
        language: str = "python",
        **kwargs: Any,
    ) -> ValidationResult:
        """Validate a fix by executing tests."""
        if language == "python":
            return await self._validate_python(original_code, fixed_code, test_code, file_path)

        # For non-Python, use LLM-based static validation
        return await self._validate_static(original_code, fixed_code, test_code, file_path)

    async def _validate_python(
        self, original_code: str, fixed_code: str, test_code: str, file_path: str
    ) -> ValidationResult:
        """Execute Python tests in a temporary environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Write fixed code
            code_file = tmp / Path(file_path).name
            code_file.write_text(fixed_code)

            # Write test file
            test_file = tmp / f"test_{Path(file_path).stem}.py"
            test_content = f"import sys\nsys.path.insert(0, '{tmpdir}')\n\n{test_code}"
            test_file.write_text(test_content)

            # Run pytest
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["python3.11", "-m", "pytest", str(test_file), "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=tmpdir,
                )

                output = result.stdout + result.stderr
                passed = result.returncode == 0

                # Count tests
                tests_run = output.count("PASSED") + output.count("FAILED") + output.count("ERROR")
                tests_passed = output.count("PASSED")
                tests_failed = output.count("FAILED") + output.count("ERROR")

                return ValidationResult(
                    passed=passed,
                    tests_run=tests_run,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed,
                    regression_detected=not passed,
                    output=output[-2000:],  # Last 2000 chars
                    recommendations=[] if passed else ["Fix did not pass all tests. Review the failures."],
                )
            except subprocess.TimeoutExpired:
                return ValidationResult(
                    passed=False,
                    tests_run=0,
                    tests_passed=0,
                    tests_failed=0,
                    regression_detected=False,
                    output="Test execution timed out (30s limit)",
                    recommendations=["Tests timed out — possible infinite loop or deadlock."],
                )
            except Exception as e:
                return ValidationResult(
                    passed=False,
                    tests_run=0,
                    tests_passed=0,
                    tests_failed=0,
                    regression_detected=False,
                    output=str(e),
                    recommendations=[f"Failed to execute tests: {e}"],
                )

    async def _validate_static(
        self, original_code: str, fixed_code: str, test_code: str, file_path: str
    ) -> ValidationResult:
        """Use LLM to statically validate a fix (for non-Python languages)."""
        prompt = (
            f"## Original Code\n```\n{original_code}\n```\n\n"
            f"## Fixed Code\n```\n{fixed_code}\n```\n\n"
            f"## Test Cases\n```\n{test_code}\n```\n\n"
            f"Would the fixed code pass these tests? Check for regressions."
        )

        return await self.generate_structured(prompt, ValidationResult)
