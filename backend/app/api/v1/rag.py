"""
RAG Q&A endpoints.

Ask natural language questions over ingested logistics documents and SOPs.
Also provides ingestion endpoints to feed data into the vector store.
"""

import json as json_module
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_qa_pipeline, get_rag_ingestor
from app.models.document import Document, DocumentStatus
from app.models.rag import RagQuery
from app.rag_engine.ingest import RAGIngestor
from app.rag_engine.qa import QAPipeline
from app.schemas.rag import RagQueryRequest, RagQueryResponse, RagStatsResponse, SourceChunk

router = APIRouter()


@router.post("/query", response_model=RagQueryResponse)
async def query_documents(
    request: RagQueryRequest,
    db: AsyncSession = Depends(get_db),
    qa_pipeline: QAPipeline = Depends(get_qa_pipeline),
) -> RagQueryResponse:
    """Ask a question over ingested logistics documents and SOPs."""
    result = await qa_pipeline.answer(request.question, db)

    # Build source chunks for response
    sources = []
    for chunk in result.chunks:
        doc_name = None
        if chunk.metadata and chunk.metadata.get("title"):
            doc_name = chunk.metadata["title"]
        sources.append(SourceChunk(
            document_id=uuid.UUID(chunk.document_id) if chunk.document_id else None,
            document_name=doc_name,
            source_type=chunk.source_type,
            snippet=chunk.content[:300],
            relevance_score=round(chunk.similarity, 3),
        ))

    # Store query in DB
    query_id = uuid.uuid4()
    rag_query = RagQuery(
        id=query_id,
        question=request.question,
        answer=result.answer,
        source_document_ids=[str(s.document_id) for s in sources if s.document_id],
        source_chunks=[s.model_dump(mode="json") for s in sources],
        model_used=result.model_used,
        processing_time_ms=result.processing_time_ms,
    )
    db.add(rag_query)
    await db.flush()

    return RagQueryResponse(
        id=query_id,
        question=request.question,
        answer=result.answer,
        sources=sources,
        model_used=result.model_used,
        processing_time_ms=result.processing_time_ms,
    )


@router.post("/ingest/seed")
async def seed_sops(
    db: AsyncSession = Depends(get_db),
    ingestor: RAGIngestor = Depends(get_rag_ingestor),
) -> dict:
    """Seed sample SOPs into the RAG knowledge base for demo purposes."""
    chunks_count = await ingestor.ingest_sample_sops(db)
    return {"chunks_ingested": chunks_count, "message": f"Seeded {chunks_count} SOP chunks"}


@router.post("/ingest/{document_id}")
async def ingest_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ingestor: RAGIngestor = Depends(get_rag_ingestor),
) -> dict:
    """Ingest a document's extraction into the RAG knowledge base."""
    # Fetch document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != DocumentStatus.EXTRACTED:
        raise HTTPException(status_code=400, detail="Document must be extracted before ingestion")

    # Get extraction data
    ext_row = (
        await db.execute(
            sa_text(
                "SELECT extraction_data, document_type FROM extractions "
                "WHERE document_id = :doc_id ORDER BY created_at DESC LIMIT 1"
            ),
            {"doc_id": document_id},
        )
    ).first()

    if ext_row is None:
        raise HTTPException(status_code=404, detail="No extraction found for this document")

    extraction_data = ext_row.extraction_data
    if isinstance(extraction_data, str):
        extraction_data = json_module.loads(extraction_data)

    chunks_count = await ingestor.ingest_extraction(
        document_id=document_id,
        extraction=extraction_data,
        doc_type=ext_row.document_type or "unknown",
        original_filename=document.original_filename,
        db=db,
    )

    return {"document_id": str(document_id), "chunks_ingested": chunks_count}


@router.get("/stats", response_model=RagStatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> RagStatsResponse:
    """Get RAG knowledge base statistics."""
    total_embeddings = (
        await db.execute(sa_text("SELECT COUNT(*) FROM embeddings WHERE embedding IS NOT NULL"))
    ).scalar() or 0

    docs_ingested = (
        await db.execute(
            sa_text("SELECT COUNT(DISTINCT document_id) FROM embeddings WHERE source_type = 'extraction'")
        )
    ).scalar() or 0

    sop_chunks = (
        await db.execute(
            sa_text("SELECT COUNT(*) FROM embeddings WHERE source_type = 'sop'")
        )
    ).scalar() or 0

    total_queries = (
        await db.execute(sa_text("SELECT COUNT(*) FROM rag_queries"))
    ).scalar() or 0

    return RagStatsResponse(
        total_embeddings=total_embeddings,
        total_documents_ingested=docs_ingested,
        total_sop_chunks=sop_chunks,
        total_queries=total_queries,
    )
