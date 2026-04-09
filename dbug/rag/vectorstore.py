"""ChromaDB vector store with incremental indexing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from dbug.rag.chunker import CodeChunk
from dbug.rag.embedder import Embedder

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB-backed vector store. Persistent, local, free."""

    def __init__(
        self,
        persist_path: str = "./chroma_db",
        collection_name: str = "dbug_code",
        embedder: Optional[Embedder] = None,
    ) -> None:
        self.persist_path = persist_path
        self.collection_name = collection_name
        self.embedder = embedder or Embedder()
        self._client: Any = None
        self._collection: Any = None

    def _get_collection(self) -> Any:
        if self._collection is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=self.persist_path)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def index_chunks(self, chunks: list[CodeChunk]) -> int:
        """Index code chunks. Returns count of newly indexed chunks."""
        if not chunks:
            return 0

        collection = self._get_collection()
        existing_ids = set(collection.get()["ids"])

        new_chunks = [c for c in chunks if c.id not in existing_ids]
        if not new_chunks:
            logger.info("All chunks already indexed")
            return 0

        # Batch embed
        texts = [c.content for c in new_chunks]
        embeddings = self.embedder.embed(texts)

        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(new_chunks), batch_size):
            batch = new_chunks[i : i + batch_size]
            batch_embeddings = embeddings[i : i + batch_size]

            collection.add(
                ids=[c.id for c in batch],
                documents=[c.content for c in batch],
                embeddings=batch_embeddings,
                metadatas=[c.to_metadata() for c in batch],
            )

        logger.info(f"Indexed {len(new_chunks)} new chunks ({len(existing_ids)} existing)")
        return len(new_chunks)

    def query(
        self,
        query_text: str,
        top_k: int = 10,
        filter_metadata: Optional[dict] = None,
        min_similarity: float = 0.35,
    ) -> list[dict[str, Any]]:
        """Query for similar code chunks."""
        collection = self._get_collection()
        query_embedding = self.embedder.embed_single(query_text)

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if filter_metadata:
            kwargs["where"] = filter_metadata

        results = collection.query(**kwargs)

        # Convert to list of dicts, filter by similarity
        items = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            similarity = 1 - distance  # ChromaDB cosine distance = 1 - similarity

            if similarity < min_similarity:
                continue

            items.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "similarity": round(similarity, 4),
            })

        return items

    def delete_file(self, file_path: str) -> int:
        """Delete all chunks for a file. Returns count deleted."""
        collection = self._get_collection()
        results = collection.get(where={"file_path": file_path})
        if results["ids"]:
            collection.delete(ids=results["ids"])
        return len(results["ids"])

    def clear(self) -> None:
        """Delete all data."""
        if self._client:
            self._client.delete_collection(self.collection_name)
            self._collection = None

    @property
    def count(self) -> int:
        return self._get_collection().count()
