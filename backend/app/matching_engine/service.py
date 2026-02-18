"""
3-way matching service.

Orchestrates PO-BOL/PackingList-Invoice matching using document relationships
to find linked documents and pure matching functions for comparison.
"""

import json as json_module
import logging
from dataclasses import dataclass

from sqlalchemy import select, or_
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.matching_engine.matchers import MatchResult, compute_three_way_match
from app.models.document import Document
from app.models.document_relationship import DocumentRelationship

logger = logging.getLogger("gamma.matching_engine")


@dataclass
class MatchInput:
    """Input documents for 3-way matching."""

    po_document_id: str | None = None
    bol_document_id: str | None = None
    invoice_document_id: str | None = None


class ThreeWayMatchingService:
    """Orchestrates 3-way PO-BOL-Invoice matching."""

    async def match(
        self,
        db: AsyncSession,
        po_document_id: str | None = None,
        bol_document_id: str | None = None,
        invoice_document_id: str | None = None,
        tolerances: dict | None = None,
    ) -> MatchResult:
        """Run 3-way matching on provided document IDs.

        At least 2 of 3 document IDs must be provided.
        """
        po_data = None
        bol_data = None
        invoice_data = None

        if po_document_id:
            po_data = await self._get_extraction(db, po_document_id)
        if bol_document_id:
            bol_data = await self._get_extraction(db, bol_document_id)
        if invoice_document_id:
            invoice_data = await self._get_extraction(db, invoice_document_id)

        return compute_three_way_match(po_data, bol_data, invoice_data, tolerances)

    async def match_from_relationships(
        self,
        db: AsyncSession,
        document_id: str,
        tolerances: dict | None = None,
    ) -> MatchResult:
        """Auto-detect related documents via DocumentRelationship and run matching.

        Finds linked PO, BOL, and Invoice for the given document.
        """
        # Get the document to know its type
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            from app.matching_engine.matchers import MatchStatus
            return MatchResult(
                status=MatchStatus.INCOMPLETE,
                overall_confidence=0.0,
                notes=["Document not found"],
            )

        # Find all related documents
        rels_result = await db.execute(
            select(DocumentRelationship).where(
                or_(
                    DocumentRelationship.source_document_id == document_id,
                    DocumentRelationship.target_document_id == document_id,
                )
            )
        )
        relationships = list(rels_result.scalars().all())

        # Collect document IDs by type
        doc_ids_by_type: dict[str, str] = {}
        doc_ids_by_type[document.document_type] = str(document.id)

        for rel in relationships:
            other_id = (
                rel.target_document_id
                if str(rel.source_document_id) == str(document_id)
                else rel.source_document_id
            )
            other_result = await db.execute(
                select(Document).where(Document.id == other_id)
            )
            other_doc = other_result.scalar_one_or_none()
            if other_doc and other_doc.document_type:
                doc_ids_by_type[other_doc.document_type] = str(other_doc.id)

        return await self.match(
            db,
            po_document_id=doc_ids_by_type.get("purchase_order"),
            bol_document_id=doc_ids_by_type.get("bill_of_lading") or doc_ids_by_type.get("packing_list"),
            invoice_document_id=doc_ids_by_type.get("commercial_invoice"),
            tolerances=tolerances,
        )

    async def _get_extraction(self, db: AsyncSession, document_id: str) -> dict | None:
        """Load extraction data for a document."""
        row = (
            await db.execute(
                sa_text(
                    "SELECT extraction_data FROM extractions "
                    "WHERE document_id = :doc_id ORDER BY created_at DESC LIMIT 1"
                ),
                {"doc_id": document_id},
            )
        ).first()

        if row is None:
            return None

        data = row.extraction_data
        if isinstance(data, str):
            data = json_module.loads(data)
        return data
