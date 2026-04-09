"""Base agent class with LLM integration and structured output."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, TypeVar

from pydantic import BaseModel

from dbug.llm import LLMBase, LLMResponse, get_llm

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AgentBase(ABC):
    """Base class for all D-BUG agents."""

    name: str = "base"
    system_prompt: str = "You are an expert software debugging agent."

    def __init__(self, llm: Optional[LLMBase] = None) -> None:
        self._llm = llm

    @property
    def llm(self) -> LLMBase:
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate a response."""
        return await self.llm.generate(
            prompt=prompt,
            system=self.system_prompt,
            **kwargs,
        )

    async def generate_structured(
        self, prompt: str, schema: type[T], **kwargs: Any
    ) -> T:
        """Generate a structured response matching a Pydantic model."""
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_prompt = (
            f"{prompt}\n\n"
            f"Respond with valid JSON matching this schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Return ONLY the JSON object, no other text."
        )

        response = await self.llm.generate(
            prompt=full_prompt,
            system=self.system_prompt,
            json_mode=True,
            **kwargs,
        )

        # Parse response
        try:
            content = response.content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(content)
            return schema.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to parse structured output: {e}\nRaw: {response.content[:500]}")
            raise ValueError(f"Agent {self.name} failed to produce valid structured output") from e

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the agent's task."""
        ...
