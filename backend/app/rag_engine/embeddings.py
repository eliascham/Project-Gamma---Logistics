"""
Embedding service wrapping Voyage AI.

Converts text into numerical vectors for semantic similarity search.
Uses Voyage 3 (1024-dim) by default — Anthropic's recommended embedding model.
"""

import logging

import voyageai

from app.config import Settings

logger = logging.getLogger("gamma.rag.embeddings")


class EmbeddingService:
    """Generate embeddings using the Voyage AI API."""

    def __init__(self, settings: Settings):
        self.client = voyageai.Client(api_key=settings.voyage_api_key)
        self.model = settings.voyage_model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for document chunks.

        Uses input_type="document" which optimizes for storage/indexing.
        Voyage recommends this for content being stored in a vector DB.
        """
        if not texts:
            return []

        logger.info("Embedding %d text chunks with %s...", len(texts), self.model)

        # Voyage SDK is synchronous, but wrapping is fine for our use case
        result = self.client.embed(texts, model=self.model, input_type="document")
        return result.embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Generate an embedding for a search query.

        Uses input_type="query" which optimizes for retrieval matching.
        This asymmetric approach (document vs query) improves retrieval quality.
        """
        result = self.client.embed([query], model=self.model, input_type="query")
        return result.embeddings[0]
