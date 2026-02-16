"""
Vector search retriever using pgvector.

Embeds a user query and finds the most semantically similar document chunks
stored in the embeddings table.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag_engine.embeddings import EmbeddingService

logger = logging.getLogger("gamma.rag.retriever")


@dataclass
class RetrievedChunk:
    """A chunk retrieved from the vector store."""

    embedding_id: str
    document_id: str | None
    content: str
    source_type: str
    metadata: dict | None
    similarity: float


class DocumentRetriever:
    """Retrieves relevant document chunks using pgvector cosine similarity."""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service

    async def search(
        self, query: str, db: AsyncSession, top_k: int = 5
    ) -> list[RetrievedChunk]:
        """Embed query and search for similar chunks.

        The query uses pgvector's <=> operator (cosine distance).
        Similarity = 1 - distance, so higher is better.
        """
        query_embedding = await self.embedding_service.embed_query(query)

        # Format embedding as pgvector literal: '[0.1, 0.2, ...]'
        vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        result = await db.execute(
            sa_text("""
                SELECT id, document_id, content, source_type, metadata,
                       1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
                FROM embeddings
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:query_vec AS vector)
                LIMIT :top_k
            """),
            {"query_vec": vec_str, "top_k": top_k},
        )

        chunks = []
        for row in result:
            chunks.append(RetrievedChunk(
                embedding_id=str(row.id),
                document_id=str(row.document_id) if row.document_id else None,
                content=row.content or "",
                source_type=row.source_type or "unknown",
                metadata=row.metadata,
                similarity=row.similarity,
            ))

        logger.info(
            "Retrieved %d chunks for query (top similarity: %.3f)",
            len(chunks),
            chunks[0].similarity if chunks else 0,
        )
        return chunks
