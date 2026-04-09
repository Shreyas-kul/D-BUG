"""Abstract base class for all LLM providers."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    raw: Optional[dict[str, Any]] = field(default=None, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMBase(ABC):
    """Base class for LLM providers. All providers implement this interface."""

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model
        self._kwargs = kwargs
        self._total_tokens_used = 0

    @abstractmethod
    async def _call(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Make the actual API call. Subclasses implement this."""
        ...

    async def generate(
        self,
        prompt: str,
        system: str = "You are a senior software engineer and expert debugger.",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a response from the LLM. Checks cache first."""
        # Check cache
        from dbug.llm.cache import get_cache

        cache = get_cache()
        cached = cache.get(prompt, system, self.model, json_mode)
        if cached:
            cached.latency_ms = 0.0  # Instant
            return cached

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        start = time.perf_counter()
        response = await self._call(messages, temperature, max_tokens, json_mode)
        response.latency_ms = (time.perf_counter() - start) * 1000
        self._total_tokens_used += response.total_tokens

        # Store in cache
        cache.put(prompt, system, self.model, json_mode, response)

        return response

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Multi-turn chat."""
        start = time.perf_counter()
        response = await self._call(messages, temperature, max_tokens, json_mode)
        response.latency_ms = (time.perf_counter() - start) * 1000
        self._total_tokens_used += response.total_tokens
        return response

    @property
    def tokens_used(self) -> int:
        return self._total_tokens_used

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and reachable."""
        ...
