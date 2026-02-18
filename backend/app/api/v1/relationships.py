"""
Document relationship endpoints.

CRUD for document relationships (links between logistics documents).
Auto-detection of relationships based on reference numbers after extraction.
"""

import json as json_module
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.document import Document
from app.models.document_relationship import (
    DocumentRelationship,
    RelationshipType,
)
from app.schemas.document_relationship import (
    DocumentRelationshipCreate,
    DocumentRelationshipResponse,
)

router = APIRouter()

# Reference fields to search for per document type, and which relationship types to create.
# Maps (doc_type, extracted_field_name) -> (relationship_type, target_doc_type_that_has_this_as_primary_key_field)
_REFERENCE_FIELD_MAP: dict[str, list[tuple[str, str, str]]] = {
    # doc_type: [(extracted_field, target_field_to_match, relationship_type), ...]
    "commercial_invoice": [
        ("transport_reference", "bol_number", "supports"),
        ("transport_reference", "awb_number", "supports"),
    ],
    "packing_list": [
        ("invoice_number", "invoice_number", "supports"),
        ("po_number", "po_number", "supports"),
        ("transport_reference", "bol_number", "supports"),
    ],
    "arrival_notice": [
        ("bol_number", "bol_number", "notifies"),
    ],
    "debit_credit_note": [
        ("original_invoice_number", "invoice_number", "adjusts"),
    ],
    "customs_entry": [
        ("bol_or_awb", "bol_number", "clears"),
        ("bol_or_awb", "awb_number", "clears"),
    ],
    "proof_of_delivery": [
        ("bol_number", "bol_number", "confirms"),
        ("order_number", "po_number", "confirms"),
    ],
    "certificate_of_origin": [
        ("invoice_number", "invoice_number", "certifies"),
    ],
}

# Primary reference field per document type (used as matching target)
_PRIMARY_REF_FIELDS: dict[str, str] = {
    "freight_invoice": "invoice_number",
    "bill_of_lading": "bol_number",
    "commercial_invoice": "invoice_number",
    "purchase_order": "po_number",
    "air_waybill": "awb_number",
}

# Prefixes to strip during reference number normalization
_REF_PREFIXES = ("PO-", "PO", "INV-", "INV", "BOL-", "BOL", "AWB-", "AWB", "REF-", "REF", "NO-", "NO.")


def _normalize_reference(value: str) -> str:
    """Normalize a reference number for fuzzy matching.

    Strips common prefixes, hyphens, dots, spaces, and leading zeros.
    """
    normalized = value.strip().upper()
    # Strip known prefixes (longest first to avoid partial matches)
    for prefix in sorted(_REF_PREFIXES, key=len, reverse=True):
        if normalized.startswith(prefix.upper()):
            normalized = normalized[len(prefix):]
            break
    # Remove hyphens, dots, spaces
    normalized = normalized.replace("-", "").replace(".", "").replace(" ", "")
    # Strip leading zeros
    normalized = normalized.lstrip("0") or "0"
    return normalized


@router.post("/", response_model=DocumentRelationshipResponse)
async def create_relationship(
    request: DocumentRelationshipCreate,
    db: AsyncSession = Depends(get_db),
) -> DocumentRelationshipResponse:
    """Create a document relationship manually."""
    # Prevent self-referencing relationships
    if request.source_document_id == request.target_document_id:
        raise HTTPException(status_code=400, detail="Cannot create a relationship between a document and itself")

    # Validate both documents exist
    for doc_id in [request.source_document_id, request.target_document_id]:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    # Validate relationship type
    try:
        rel_type = RelationshipType(request.relationship_type)
    except ValueError:
        valid = [t.value for t in RelationshipType]
        raise HTTPException(status_code=400, detail=f"Invalid relationship_type. Must be one of: {valid}")

    relationship = DocumentRelationship(
        id=uuid.uuid4(),
        source_document_id=request.source_document_id,
        target_document_id=request.target_document_id,
        relationship_type=rel_type,
        reference_field=request.reference_field,
        reference_value=request.reference_value,
        confidence=request.confidence,
        created_by="user",
    )
    db.add(relationship)
    await db.flush()

    return DocumentRelationshipResponse.model_validate(relationship)


@router.get("/", response_model=list[DocumentRelationshipResponse])
async def list_relationships(
    document_id: uuid.UUID | None = Query(None, description="Filter by document (source or target)"),
    relationship_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentRelationshipResponse]:
    """List document relationships, optionally filtered."""
    query = select(DocumentRelationship).order_by(DocumentRelationship.created_at.desc())

    if document_id:
        query = query.where(
            or_(
                DocumentRelationship.source_document_id == document_id,
                DocumentRelationship.target_document_id == document_id,
            )
        )
    if relationship_type:
        query = query.where(DocumentRelationship.relationship_type == relationship_type)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return [DocumentRelationshipResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/{relationship_id}", response_model=DocumentRelationshipResponse)
async def get_relationship(
    relationship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentRelationshipResponse:
    """Get a single document relationship."""
    result = await db.execute(
        select(DocumentRelationship).where(DocumentRelationship.id == relationship_id)
    )
    rel = result.scalar_one_or_none()
    if rel is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return DocumentRelationshipResponse.model_validate(rel)


@router.delete("/{relationship_id}")
async def delete_relationship(
    relationship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a document relationship."""
    result = await db.execute(
        select(DocumentRelationship).where(DocumentRelationship.id == relationship_id)
    )
    rel = result.scalar_one_or_none()
    if rel is None:
        raise HTTPException(status_code=404, detail="Relationship not found")

    await db.delete(rel)
    await db.flush()
    return {"deleted": True}


@router.post("/detect/{document_id}", response_model=list[DocumentRelationshipResponse])
async def detect_relationships(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[DocumentRelationshipResponse]:
    """Auto-detect relationships for a document based on extracted reference numbers.

    Searches existing documents for matching reference numbers and creates
    DocumentRelationship records for exact matches.
    """
    # Fetch the document
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document = doc_result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_type = document.document_type
    if not doc_type:
        return []

    # Get the extraction data
    ext_row = (
        await db.execute(
            sa_text(
                "SELECT extraction_data FROM extractions "
                "WHERE document_id = :doc_id ORDER BY created_at DESC LIMIT 1"
            ),
            {"doc_id": document_id},
        )
    ).first()

    if ext_row is None:
        return []

    extraction_data = ext_row.extraction_data
    if isinstance(extraction_data, str):
        extraction_data = json_module.loads(extraction_data)

    created: list[DocumentRelationship] = []

    # Check references defined for this document type
    ref_mappings = _REFERENCE_FIELD_MAP.get(doc_type, [])
    for extracted_field, target_field, rel_type_str in ref_mappings:
        ref_value = extraction_data.get(extracted_field)
        if not ref_value or not isinstance(ref_value, str):
            continue

        # Search all other extractions for a matching reference
        matches = await _find_documents_by_reference(db, target_field, ref_value, exclude_id=document_id)
        for target_doc_id in matches:
            # Avoid duplicates
            existing = await db.execute(
                select(DocumentRelationship).where(
                    DocumentRelationship.source_document_id == document_id,
                    DocumentRelationship.target_document_id == target_doc_id,
                    DocumentRelationship.relationship_type == rel_type_str,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            rel = DocumentRelationship(
                id=uuid.uuid4(),
                source_document_id=document_id,
                target_document_id=target_doc_id,
                relationship_type=RelationshipType(rel_type_str),
                reference_field=extracted_field,
                reference_value=ref_value,
                confidence=1.0,
                created_by="system",
            )
            db.add(rel)
            created.append(rel)

    # Also check if this document's primary reference is referenced by others
    primary_field = _PRIMARY_REF_FIELDS.get(doc_type)
    if primary_field:
        primary_value = extraction_data.get(primary_field)
        if primary_value and isinstance(primary_value, str):
            # Search for other documents that reference this value
            reverse_matches = await _find_documents_referencing(db, primary_value, exclude_id=document_id)
            for other_doc_id, other_doc_type, other_field in reverse_matches:
                # Determine the relationship type from the other doc's perspective
                other_mappings = _REFERENCE_FIELD_MAP.get(other_doc_type, [])
                for ext_f, tgt_f, r_type in other_mappings:
                    if ext_f == other_field and tgt_f == primary_field:
                        existing = await db.execute(
                            select(DocumentRelationship).where(
                                DocumentRelationship.source_document_id == other_doc_id,
                                DocumentRelationship.target_document_id == document_id,
                                DocumentRelationship.relationship_type == r_type,
                            )
                        )
                        if existing.scalar_one_or_none() is not None:
                            continue

                        rel = DocumentRelationship(
                            id=uuid.uuid4(),
                            source_document_id=other_doc_id,
                            target_document_id=document_id,
                            relationship_type=RelationshipType(r_type),
                            reference_field=other_field,
                            reference_value=primary_value,
                            confidence=1.0,
                            created_by="system",
                        )
                        db.add(rel)
                        created.append(rel)
                        break

    if created:
        await db.flush()

    return [DocumentRelationshipResponse.model_validate(r) for r in created]


async def _find_documents_by_reference(
    db: AsyncSession,
    field_name: str,
    value: str,
    exclude_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Find document IDs whose extraction contains a matching reference field value."""
    # Search extractions table using JSON field lookup
    # This works for both PostgreSQL (jsonb) and basic JSON columns
    rows = await db.execute(
        sa_text(
            "SELECT DISTINCT e.document_id FROM extractions e "
            "WHERE e.document_id != :exclude_id "
            "AND e.extraction_data IS NOT NULL"
        ),
        {"exclude_id": exclude_id},
    )

    matches = []
    for row in rows:
        doc_id = row.document_id
        # Get the extraction data to check the field
        ext_result = await db.execute(
            sa_text(
                "SELECT extraction_data FROM extractions "
                "WHERE document_id = :doc_id ORDER BY created_at DESC LIMIT 1"
            ),
            {"doc_id": doc_id},
        )
        ext_row = ext_result.first()
        if ext_row is None:
            continue

        data = ext_row.extraction_data
        if isinstance(data, str):
            data = json_module.loads(data)

        stored_value = data.get(field_name)
        if stored_value and isinstance(stored_value, str):
            if _normalize_reference(stored_value) == _normalize_reference(value):
                matches.append(doc_id)

    return matches


async def _find_documents_referencing(
    db: AsyncSession,
    value: str,
    exclude_id: uuid.UUID,
) -> list[tuple[uuid.UUID, str, str]]:
    """Find documents that reference a given value in any of their reference fields.

    Returns list of (document_id, document_type, field_name).
    """
    rows = await db.execute(
        sa_text(
            "SELECT DISTINCT e.document_id FROM extractions e "
            "JOIN documents d ON d.id = e.document_id "
            "WHERE e.document_id != :exclude_id "
            "AND e.extraction_data IS NOT NULL"
        ),
        {"exclude_id": exclude_id},
    )

    results = []
    for row in rows:
        doc_id = row.document_id

        # Get the document type
        doc_result = await db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = doc_result.scalar_one_or_none()
        if doc is None or not doc.document_type:
            continue

        # Get extraction data
        ext_result = await db.execute(
            sa_text(
                "SELECT extraction_data FROM extractions "
                "WHERE document_id = :doc_id ORDER BY created_at DESC LIMIT 1"
            ),
            {"doc_id": doc_id},
        )
        ext_row = ext_result.first()
        if ext_row is None:
            continue

        data = ext_row.extraction_data
        if isinstance(data, str):
            data = json_module.loads(data)

        # Check all reference fields for this doc type
        ref_mappings = _REFERENCE_FIELD_MAP.get(doc.document_type, [])
        for extracted_field, _target_field, _rel_type in ref_mappings:
            stored_value = data.get(extracted_field)
            if stored_value and isinstance(stored_value, str):
                if _normalize_reference(stored_value) == _normalize_reference(value):
                    results.append((doc_id, doc.document_type, extracted_field))

    return results
