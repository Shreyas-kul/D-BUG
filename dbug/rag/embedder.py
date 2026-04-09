"""Local embeddings using sentence-transformers."""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings using sentence-transformers. Runs locally on CPU. Free."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model: Optional[Any] = None

    def _get_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded embedding model: {self.model_name}")
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of vectors."""
        if not texts:
            return []

        model = self._get_model()
        embeddings = model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
            batch_size=32,
        )
        return embeddings.tolist()  # type: ignore

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text."""
        return self.embed([text])[0]

    def similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Cosine similarity between two vectors."""
        a, b = np.array(vec_a), np.array(vec_b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))
