"""
Extraction endpoints — runs the 2-pass extraction pipeline on uploaded documents.

Flow:
1. Fetch document record from DB
2. Run extraction pipeline (parse → classify → extract → review)
3. Store extraction results in extractions table
4. Update document status and type
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.document_extractor.pipeline import ExtractionPipeline
from app.models.document import Document, DocumentStatus
from app.schemas.extraction import DocumentType, ExtractionResponse

router = APIRouter()


@router.get("/{document_id}", response_model=ExtractionResponse)
async def get_extraction(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ExtractionResponse:
    """Get the latest extraction result for a document."""
    from sqlalchemy import text as sa_text

    row = (
        await db.execute(
            sa_text(
                "SELECT document_type, extraction_data, raw_extraction, model_used, "
                "processing_time_ms FROM extractions "
                "WHERE document_id = :doc_id ORDER BY created_at DESC LIMIT 1"
            ),
            {"doc_id": document_id},
        )
    ).first()

    if row is None:
        raise HTTPException(status_code=404, detail="No extraction found for this document")

    import json as json_module

    def _parse_json(val: object) -> dict:
        if val is None:
            return {}
        if isinstance(val, str):
            return json_module.loads(val)
        return dict(val)  # type: ignore[arg-type]

    return ExtractionResponse(
        document_id=document_id,
        document_type=DocumentType(row.document_type),
        extraction=_parse_json(row.extraction_data),
        raw_extraction=_parse_json(row.raw_extraction),
        model_used=row.model_used or "",
        processing_time_ms=row.processing_time_ms,
        confidence_notes=None,
    )


def _get_pipeline() -> ExtractionPipeline:
    return ExtractionPipeline(settings)


@router.post("/{document_id}", response_model=ExtractionResponse)
async def extract_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pipeline: ExtractionPipeline = Depends(_get_pipeline),
) -> ExtractionResponse:
    """Run the extraction pipeline on a document.

    This performs:
    1. Document parsing (PDF text extraction, image encoding, CSV formatting)
    2. Document classification via Haiku (freight invoice vs BOL)
    3. Pass 1: Raw data extraction via Sonnet
    4. Pass 2: Self-review and refinement via Sonnet
    """
    # Fetch the document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Update status to processing
    document.status = DocumentStatus.PROCESSING
    await db.flush()

    from app.audit_generator.service import AuditService
    await AuditService.log_event(
        db,
        event_type="EXTRACTION_STARTED",
        entity_type="document",
        entity_id=document.id,
        action="extraction_start",
        actor="system",
        actor_type="ai",
    )

    # Run the extraction pipeline
    try:
        extraction_result = await pipeline.run(
            file_path=document.file_path,
            file_type=document.file_type,
            mime_type=document.mime_type,
        )
    except FileNotFoundError:
        document.status = DocumentStatus.FAILED
        await db.flush()
        raise HTTPException(status_code=404, detail="Document file not found on disk")
    except ValueError as e:
        document.status = DocumentStatus.FAILED
        await db.flush()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        document.status = DocumentStatus.FAILED
        await db.flush()
        raise HTTPException(status_code=502, detail=f"Extraction failed: {e}")

    # Update document with results
    document.status = DocumentStatus.EXTRACTED
    document.document_type = extraction_result.document_type.value
    if extraction_result.parsed_document:
        document.page_count = extraction_result.parsed_document.page_count
    await db.flush()

    # Store extraction in extractions table
    import json as json_module
    from sqlalchemy import text as sa_text

    extraction_id = uuid.uuid4()
    await db.execute(
        sa_text("""
            INSERT INTO extractions (
                id, document_id, document_type, extraction_data,
                raw_extraction, refined_extraction,
                model_used, pass1_model, pass2_model, classifier_model,
                processing_time_ms, page_count, vision_used, metadata, created_at
            ) VALUES (
                :id, :document_id, :document_type,
                CAST(:extraction_data AS json),
                CAST(:raw_extraction AS json),
                CAST(:refined_extraction AS json),
                :model_used, :pass1_model, :pass2_model, :classifier_model,
                :processing_time_ms, :page_count, :vision_used,
                CAST(:metadata AS json), NOW()
            )
        """),
        {
            "id": extraction_id,
            "document_id": document.id,
            "document_type": extraction_result.document_type.value,
            "extraction_data": json_module.dumps(extraction_result.refined_extraction, default=str),
            "raw_extraction": json_module.dumps(extraction_result.raw_extraction, default=str),
            "refined_extraction": json_module.dumps(extraction_result.refined_extraction, default=str),
            "model_used": extraction_result.model_used,
            "pass1_model": extraction_result.model_used,
            "pass2_model": extraction_result.model_used,
            "classifier_model": extraction_result.haiku_model,
            "processing_time_ms": extraction_result.processing_time_ms,
            "page_count": extraction_result.metadata.get("page_count"),
            "vision_used": extraction_result.metadata.get("vision_used", False),
            "metadata": "{}",
        },
    )
    await db.flush()

    await AuditService.log_event(
        db,
        event_type="EXTRACTION_COMPLETED",
        entity_type="document",
        entity_id=document.id,
        action="extraction_complete",
        actor="system",
        actor_type="ai",
        model_used=extraction_result.model_used,
        new_state={
            "document_type": extraction_result.document_type.value,
            "processing_time_ms": extraction_result.processing_time_ms,
        },
    )

    return ExtractionResponse(
        document_id=document.id,
        document_type=extraction_result.document_type,
        extraction=extraction_result.refined_extraction,
        raw_extraction=extraction_result.raw_extraction,
        model_used=extraction_result.model_used,
        processing_time_ms=extraction_result.processing_time_ms,
        confidence_notes=None,
    )
