"""Hybrid retriever — vector similarity + AST dependency resolution."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from dbug.rag.chunker import ASTChunker, CodeChunk
from dbug.rag.vectorstore import VectorStore

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Retrieves relevant code using vector search + dependency graph traversal."""

    def __init__(
        self,
        vectorstore: Optional[VectorStore] = None,
        chunker: Optional[ASTChunker] = None,
        top_k: int = 10,
        min_similarity: float = 0.35,
    ) -> None:
        self.vectorstore = vectorstore or VectorStore()
        self.chunker = chunker or ASTChunker()
        self.top_k = top_k
        self.min_similarity = min_similarity
        self._indexed_chunks: dict[str, CodeChunk] = {}

    def index_codebase(self, path: Path) -> int:
        """Index an entire codebase directory."""
        chunks = self.chunker.chunk_directory(path)
        for chunk in chunks:
            self._indexed_chunks[chunk.id] = chunk
        return self.vectorstore.index_chunks(chunks)

    def index_file(self, file_path: Path) -> int:
        """Index or re-index a single file."""
        # Remove old chunks for this file
        self.vectorstore.delete_file(str(file_path))
        # Chunk and re-index
        chunks = self.chunker.chunk_file(file_path)
        for chunk in chunks:
            self._indexed_chunks[chunk.id] = chunk
        return self.vectorstore.index_chunks(chunks)

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        file_filter: Optional[str] = None,
        include_dependencies: bool = True,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant code chunks for a query.

        Args:
            query: Natural language or code query.
            top_k: Number of results to return.
            file_filter: Only return chunks from this file.
            include_dependencies: Also retrieve chunks that the results depend on.

        Returns:
            List of dicts with 'content', 'metadata', 'similarity'.
        """
        k = top_k or self.top_k
        filter_meta = {"file_path": file_filter} if file_filter else None

        results = self.vectorstore.query(
            query_text=query,
            top_k=k,
            filter_metadata=filter_meta,
            min_similarity=self.min_similarity,
        )

        if include_dependencies and results:
            results = self._resolve_dependencies(results)

        return results

    def _resolve_dependencies(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """For each result, also fetch code it depends on."""
        seen_ids = {r["id"] for r in results}
        additional: list[dict[str, Any]] = []

        for result in results:
            chunk = self._indexed_chunks.get(result["id"])
            if not chunk or not chunk.dependencies:
                continue

            # Search for dependency definitions
            for dep in chunk.dependencies[:5]:  # Limit to avoid explosion
                dep_results = self.vectorstore.query(
                    query_text=dep, top_k=2, min_similarity=0.5
                )
                for dr in dep_results:
                    if dr["id"] not in seen_ids:
                        dr["_is_dependency"] = True
                        additional.append(dr)
                        seen_ids.add(dr["id"])

        return results + additional

    def get_context_window(self, query: str, max_tokens: int = 4000) -> str:
        """Get a formatted context window for LLM consumption."""
        results = self.retrieve(query)
        context_parts = []
        total_chars = 0
        char_limit = max_tokens * 4  # Rough token-to-char ratio

        for r in results:
            content = r["content"]
            meta = r["metadata"]
            header = f"# {meta.get('file_path', '?')}:{meta.get('start_line', '?')}-{meta.get('end_line', '?')}"
            block = f"{header}\n```{meta.get('language', '')}\n{content}\n```\n"

            if total_chars + len(block) > char_limit:
                break
            context_parts.append(block)
            total_chars += len(block)

        return "\n".join(context_parts)
