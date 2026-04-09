"""HuggingFace Inference API provider — Free tier fallback."""

from __future__ import annotations

import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from dbug.llm.base import LLMBase, LLMResponse

logger = logging.getLogger(__name__)


class HuggingFaceProvider(LLMBase):
    """HuggingFace Inference API. Free tier: rate-limited but functional."""

    def __init__(
        self, model: str = "Qwen/Qwen2.5-Coder-32B-Instruct", **kwargs: Any
    ) -> None:
        super().__init__(model, **kwargs)
        self._api_token = kwargs.get("api_token", "")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from huggingface_hub import AsyncInferenceClient

            self._client = AsyncInferenceClient(
                model=self.model, token=self._api_token or None
            )
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=60))
    async def _call(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_client()
        response = await client.chat_completion(
            messages=messages,
            temperature=max(temperature, 0.01),  # HF requires > 0
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            model=self.model,
            provider="huggingface",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            raw=None,
        )

    def is_available(self) -> bool:
        return bool(self._api_token)
