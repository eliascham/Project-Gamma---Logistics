"""Pydantic schemas for RAG Q&A API requests and responses."""

from uuid import UUID

from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


class SourceChunk(BaseModel):
    document_id: UUID | None = None
    document_name: str | None = None
    source_type: str
    snippet: str
    relevance_score: float


class RagQueryResponse(BaseModel):
    id: UUID
    question: str
    answer: str
    sources: list[SourceChunk] = []
    model_used: str
    processing_time_ms: int


class RagStatsResponse(BaseModel):
    total_embeddings: int
    total_documents_ingested: int
    total_sop_chunks: int
    total_queries: int
