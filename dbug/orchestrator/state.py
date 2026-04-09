"""Pipeline state schema."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    INIT = "init"
    SCANNING = "scanning"
    ADVERSARIAL = "adversarial_testing"
    ROOT_CAUSE = "root_cause_analysis"
    FIX_GENERATION = "fix_generation"
    VALIDATION = "validation"
    COMPLETE = "complete"
    FAILED = "failed"


class BugReport(BaseModel):
    """A single bug found during the pipeline."""

    id: str
    title: str
    file_path: str
    start_line: int
    end_line: int
    severity: str  # critical, high, medium, low
    category: str
    root_cause: str = ""
    test_code: str = ""
    fix_diff: str = ""
    fix_code: str = ""
    fix_validated: bool = False
    confidence: float = 0.0


class PipelineState(BaseModel):
    """State passed between pipeline stages."""

    # Pipeline tracking
    stage: PipelineStage = PipelineStage.INIT
    target_path: str = "."
    retry_count: int = 0
    max_retries: int = 3

    # Scan results
    total_files: int = 0
    total_chunks: int = 0
    languages: list[str] = Field(default_factory=list)
    high_risk_areas: list[dict[str, Any]] = Field(default_factory=list)

    # Bug tracking
    bugs: list[BugReport] = Field(default_factory=list)
    current_bug_index: int = 0

    # Metrics
    tokens_used: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def current_bug(self) -> Optional[BugReport]:
        if 0 <= self.current_bug_index < len(self.bugs):
            return self.bugs[self.current_bug_index]
        return None

    @property
    def bugs_fixed(self) -> int:
        return sum(1 for b in self.bugs if b.fix_validated)

    @property
    def bugs_found(self) -> int:
        return len(self.bugs)
