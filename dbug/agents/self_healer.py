"""Self-healing mode — auto-applies fixes and creates git commits."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from dbug.orchestrator.state import BugReport

logger = logging.getLogger(__name__)


class SelfHealer:
    """Auto-apply fixes to source code and commit them."""

    def __init__(self, repo_path: str = ".") -> None:
        self.repo_path = Path(repo_path)

    def apply_fix(self, bug: BugReport, dry_run: bool = False) -> bool:
        """Apply a fix to the source file."""
        if not bug.fix_code or not bug.fix_validated:
            return False

        file_path = Path(bug.file_path)
        if not file_path.exists():
            return False

        try:
            source = file_path.read_text(encoding="utf-8")
            lines = source.splitlines(keepends=True)

            # Replace the buggy lines
            start = max(0, bug.start_line - 1)
            end = bug.end_line

            if dry_run:
                logger.info(f"[DRY RUN] Would fix {file_path}:{start+1}-{end}")
                return True

            # Write the fix
            new_lines = lines[:start] + [bug.fix_code + "\n"] + lines[end:]
            file_path.write_text("".join(new_lines), encoding="utf-8")
            logger.info(f"✅ Applied fix to {file_path}:{start+1}-{end}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply fix: {e}")
            return False

    def commit_fixes(self, bugs: list[BugReport], message: Optional[str] = None) -> bool:
        """Git commit all applied fixes."""
        fixed = [b for b in bugs if b.fix_validated]
        if not fixed:
            return False

        msg = message or f"🐛 D-BUG: Auto-fixed {len(fixed)} bug(s)\n\n"
        for b in fixed:
            msg += f"- [{b.severity.upper()}] {b.title} ({Path(b.file_path).name}:{b.start_line})\n"

        try:
            subprocess.run(["git", "add", "-A"], cwd=self.repo_path, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=self.repo_path, check=True, capture_output=True,
            )
            logger.info(f"📝 Committed {len(fixed)} fixes")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Git commit failed: {e.stderr}")
            return False
