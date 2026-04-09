"""LLM response cache — never pay for the same prompt twice."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

from dbug.llm.base import LLMResponse

logger = logging.getLogger(__name__)


class LLMCache:
    """SQLite-backed LLM response cache. Persistent across runs."""

    def __init__(self, db_path: str = ".dbug_cache.db", ttl_hours: int = 72) -> None:
        self.db_path = db_path
        self.ttl_seconds = ttl_hours * 3600
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_cache (
                key TEXT PRIMARY KEY,
                response TEXT NOT NULL,
                model TEXT,
                provider TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created ON llm_cache(created_at)
        """)
        self._conn.commit()

    @staticmethod
    def _make_key(prompt: str, system: str, model: str, json_mode: bool) -> str:
        raw = f"{model}|{system}|{prompt}|{json_mode}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, prompt: str, system: str, model: str, json_mode: bool = False) -> Optional[LLMResponse]:
        """Get cached response. Returns None if not found or expired."""
        key = self._make_key(prompt, system, model, json_mode)
        cursor = self._conn.execute(
            "SELECT response, model, provider, input_tokens, output_tokens, created_at "
            "FROM llm_cache WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Check TTL
        if time.time() - row[5] > self.ttl_seconds:
            self._conn.execute("DELETE FROM llm_cache WHERE key = ?", (key,))
            self._conn.commit()
            return None

        logger.debug(f"Cache HIT (saved {row[3] + row[4]} tokens)")
        return LLMResponse(
            content=row[0],
            model=row[1],
            provider=row[2],
            input_tokens=row[3],
            output_tokens=row[4],
        )

    def put(self, prompt: str, system: str, model: str, json_mode: bool, response: LLMResponse) -> None:
        """Cache an LLM response."""
        key = self._make_key(prompt, system, model, json_mode)
        self._conn.execute(
            "INSERT OR REPLACE INTO llm_cache (key, response, model, provider, input_tokens, output_tokens, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key, response.content, response.model, response.provider,
             response.input_tokens, response.output_tokens, time.time()),
        )
        self._conn.commit()

    def clear(self) -> None:
        """Clear all cached responses."""
        self._conn.execute("DELETE FROM llm_cache")
        self._conn.commit()
        logger.info("Cache cleared")

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count deleted."""
        cutoff = time.time() - self.ttl_seconds
        cursor = self._conn.execute("DELETE FROM llm_cache WHERE created_at < ?", (cutoff,))
        self._conn.commit()
        return cursor.rowcount

    @property
    def stats(self) -> dict:
        """Cache statistics."""
        row = self._conn.execute(
            "SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens) FROM llm_cache"
        ).fetchone()
        return {
            "entries": row[0] or 0,
            "total_input_tokens_saved": row[1] or 0,
            "total_output_tokens_saved": row[2] or 0,
        }


# Singleton
_cache: Optional[LLMCache] = None


def get_cache() -> LLMCache:
    global _cache
    if _cache is None:
        _cache = LLMCache()
    return _cache
