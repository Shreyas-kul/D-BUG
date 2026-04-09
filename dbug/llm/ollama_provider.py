"""Ollama LLM provider — Free local inference."""

from __future__ import annotations

import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from dbug.llm.base import LLMBase, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(LLMBase):
    """Ollama local inference. Zero cost. Requires `ollama` running locally."""

    def __init__(self, model: str = "deepseek-coder-v2:latest", **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._host = kwargs.get("host", "http://localhost:11434")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from ollama import AsyncClient

            self._client = AsyncClient(host=self._host)
        return self._client

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
    async def _call(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            kwargs["format"] = "json"

        response = await client.chat(**kwargs)
        return LLMResponse(
            content=response.get("message", {}).get("content", ""),
            model=self.model,
            provider="ollama",
            input_tokens=response.get("prompt_eval_count", 0),
            output_tokens=response.get("eval_count", 0),
            raw=response,
        )

    def is_available(self) -> bool:
        try:
            import httpx

            r = httpx.get(f"{self._host}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False
