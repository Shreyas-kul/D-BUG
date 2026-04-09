"""Watch mode — monitor file changes and auto-scan in real-time."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FileWatcher:
    """Watch for file changes and trigger scans automatically."""

    def __init__(
        self,
        path: str = ".",
        on_change: Optional[Callable] = None,
        debounce_seconds: float = 2.0,
    ) -> None:
        self.path = Path(path)
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds
        self._file_mtimes: dict[str, float] = {}
        self._running = False

    def _snapshot(self) -> dict[str, float]:
        """Get current modification times for all tracked files."""
        mtimes: dict[str, float] = {}
        extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c"}
        exclude = {".git", "__pycache__", "node_modules", ".venv", "venv", "chroma_db"}

        for f in self.path.rglob("*"):
            if f.is_file() and f.suffix in extensions:
                if not any(part in exclude for part in f.parts):
                    try:
                        mtimes[str(f)] = f.stat().st_mtime
                    except OSError:
                        pass
        return mtimes

    def _detect_changes(self) -> list[str]:
        """Detect which files changed since last snapshot."""
        current = self._snapshot()
        changed: list[str] = []

        for path, mtime in current.items():
            if path not in self._file_mtimes or self._file_mtimes[path] != mtime:
                changed.append(path)

        # Detect deleted files
        for path in self._file_mtimes:
            if path not in current:
                changed.append(path)

        self._file_mtimes = current
        return changed

    async def watch(self) -> None:
        """Start watching for changes. Runs forever."""
        self._running = True
        self._file_mtimes = self._snapshot()
        logger.info(f"👁️ Watching {self.path} for changes... (Ctrl+C to stop)")

        while self._running:
            await asyncio.sleep(self.debounce_seconds)

            changed = self._detect_changes()
            if changed and self.on_change:
                logger.info(f"📝 {len(changed)} file(s) changed: {', '.join(Path(f).name for f in changed[:5])}")
                try:
                    await self.on_change(changed)
                except Exception as e:
                    logger.error(f"Watch callback error: {e}")

    def stop(self) -> None:
        self._running = False
