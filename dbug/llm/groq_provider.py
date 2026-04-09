"""Groq LLM provider — Free Llama 3.3 70B inference."""

from __future__ import annotations

import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from dbug.llm.base import LLMBase, LLMResponse

logger = logging.getLogger(__name__)


class GroqProvider(LLMBase):
    """Groq cloud inference. Free tier: 30 requests/min."""

    def __init__(self, model: str = "llama-3.3-70b-versatile", **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._api_key = kwargs.get("api_key", "")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from groq import AsyncGroq

            self._client = AsyncGroq(api_key=self._api_key)
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def _call(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            model=self.model,
            provider="groq",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def is_available(self) -> bool:
        return bool(self._api_key)
