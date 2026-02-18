"""
3-way matching endpoints.

Run PO-BOL-Invoice matching and view results.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_three_way_matching_service
from app.matching_engine.service import ThreeWayMatchingService

router = APIRouter()


class MatchRequest(BaseModel):
    po_document_id: uuid.UUID | None = Field(None, description="Purchase Order document ID")
    bol_document_id: uuid.UUID | None = Field(None, description="BOL or Packing List document ID")
    invoice_document_id: uuid.UUID | None = Field(None, description="Commercial Invoice document ID")


class FieldMatchResponse(BaseModel):
    field_name: str
    matched: bool
    confidence: float
    po_value: str | float | None = None
    bol_value: str | float | None = None
    invoice_value: str | float | None = None
    note: str | None = None


class LineItemMatchResponse(BaseModel):
    po_index: int | None = None
    invoice_index: int | None = None
    description_match: float = 0.0
    quantity_match: float = 0.0
    unit_price_match: float = 0.0
    overall: float = 0.0
    notes: list[str] = []


class MatchResultResponse(BaseModel):
    status: str
    overall_confidence: float
    field_matches: list[FieldMatchResponse] = []
    line_item_matches: list[LineItemMatchResponse] = []
    missing_documents: list[str] = []
    notes: list[str] = []


@router.post("/run", response_model=MatchResultResponse)
async def run_match(
    request: MatchRequest,
    db: AsyncSession = Depends(get_db),
    service: ThreeWayMatchingService = Depends(get_three_way_matching_service),
) -> MatchResultResponse:
    """Run 3-way PO-BOL-Invoice matching.

    Provide at least 2 of 3 document IDs. Returns match status and per-field scores.
    """
    provided = sum(1 for x in [request.po_document_id, request.bol_document_id, request.invoice_document_id] if x)
    if provided < 2:
        raise HTTPException(status_code=400, detail="At least 2 of 3 document IDs are required")

    result = await service.match(
        db,
        po_document_id=str(request.po_document_id) if request.po_document_id else None,
        bol_document_id=str(request.bol_document_id) if request.bol_document_id else None,
        invoice_document_id=str(request.invoice_document_id) if request.invoice_document_id else None,
    )

    return _to_response(result)


@router.post("/auto/{document_id}", response_model=MatchResultResponse)
async def auto_match(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    service: ThreeWayMatchingService = Depends(get_three_way_matching_service),
) -> MatchResultResponse:
    """Auto-detect related documents and run 3-way matching.

    Uses DocumentRelationship links to find the PO, BOL, and Invoice for a document.
    """
    result = await service.match_from_relationships(
        db, str(document_id)
    )
    return _to_response(result)


def _to_response(result) -> MatchResultResponse:
    """Convert MatchResult to API response."""
    return MatchResultResponse(
        status=result.status.value,
        overall_confidence=result.overall_confidence,
        field_matches=[
            FieldMatchResponse(
                field_name=fm.field_name,
                matched=fm.matched,
                confidence=fm.confidence,
                po_value=fm.po_value,
                bol_value=fm.bol_value,
                invoice_value=fm.invoice_value,
                note=fm.note,
            )
            for fm in result.field_matches
        ],
        line_item_matches=[
            LineItemMatchResponse(
                po_index=lm.po_index,
                invoice_index=lm.invoice_index,
                description_match=lm.description_match,
                quantity_match=lm.quantity_match,
                unit_price_match=lm.unit_price_match,
                overall=lm.overall,
                notes=lm.notes,
            )
            for lm in result.line_item_matches
        ],
        missing_documents=result.missing_documents,
        notes=result.notes,
    )
