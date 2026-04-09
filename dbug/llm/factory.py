"""LLM provider factory with auto-fallback chain."""

from __future__ import annotations

import logging
from typing import Optional

from dbug.config import LLMProvider, Settings, get_settings
from dbug.llm.base import LLMBase

logger = logging.getLogger(__name__)

_PROVIDER_CACHE: dict[str, LLMBase] = {}


def _create_provider(provider: LLMProvider, settings: Settings) -> LLMBase:
    """Create a provider instance."""
    if provider == LLMProvider.GROQ:
        from dbug.llm.groq_provider import GroqProvider

        return GroqProvider(model=settings.groq_model, api_key=settings.groq_api_key or "")

    elif provider == LLMProvider.OLLAMA:
        from dbug.llm.ollama_provider import OllamaProvider

        return OllamaProvider(model=settings.ollama_model, host=settings.ollama_host)

    elif provider == LLMProvider.HUGGINGFACE:
        from dbug.llm.huggingface_provider import HuggingFaceProvider

        return HuggingFaceProvider(
            model=settings.hf_model, api_token=settings.hf_api_token or ""
        )

    raise ValueError(f"Unknown provider: {provider}")


def get_llm(
    provider: Optional[str] = None,
    fast: bool = False,
    settings: Optional[Settings] = None,
) -> LLMBase:
    """Get an LLM provider with auto-fallback.

    Args:
        provider: Force a specific provider. If None, uses config + fallback.
        fast: Use the faster/smaller model variant.
        settings: Override settings. Defaults to global settings.

    Returns:
        A ready-to-use LLM provider.

    Raises:
        RuntimeError: If no provider is available.
    """
    settings = settings or get_settings()

    if provider:
        p = LLMProvider(provider)
        llm = _create_provider(p, settings)
        if fast and p == LLMProvider.GROQ:
            llm.model = settings.groq_fast_model
        return llm

    # Auto-fallback chain: Groq → Ollama → HuggingFace
    fallback_order = [LLMProvider.GROQ, LLMProvider.OLLAMA, LLMProvider.HUGGINGFACE]

    # Start with user's preferred provider
    preferred = settings.llm_provider
    if preferred in fallback_order:
        fallback_order.remove(preferred)
        fallback_order.insert(0, preferred)

    for p in fallback_order:
        cache_key = f"{p.value}:{fast}"
        if cache_key in _PROVIDER_CACHE:
            return _PROVIDER_CACHE[cache_key]

        try:
            llm = _create_provider(p, settings)
            if not llm.is_available():
                logger.debug(f"Provider {p.value} not available, trying next...")
                continue
            if fast and p == LLMProvider.GROQ:
                llm.model = settings.groq_fast_model
            _PROVIDER_CACHE[cache_key] = llm
            logger.info(f"Using LLM provider: {p.value} (model: {llm.model})")
            return llm
        except Exception as e:
            logger.warning(f"Failed to initialize {p.value}: {e}")
            continue

    raise RuntimeError(
        "No LLM provider available. Set GROQ_API_KEY, install Ollama, "
        "or set HF_API_TOKEN. See .env.example for details."
    )


def clear_cache() -> None:
    """Clear the provider cache."""
    _PROVIDER_CACHE.clear()
