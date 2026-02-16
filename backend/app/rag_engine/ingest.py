"""
RAG ingestion — feeds document data and SOPs into the vector store.

Supports:
- Ingesting extraction results (converts structured data → natural language → chunks → embeddings)
- Ingesting sample SOPs for demo purposes
"""

import json
import logging
import uuid

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.rag_engine.chunker import chunk_text, extraction_to_text
from app.rag_engine.embeddings import EmbeddingService

logger = logging.getLogger("gamma.rag.ingest")

# Sample SOPs for demo — realistic logistics operations procedures
SAMPLE_SOPS = [
    {
        "title": "SOP-001: International Freight Invoice Processing",
        "content": (
            "International Freight Invoice Processing Procedure. "
            "All freight invoices must be processed and allocated within 48 hours of receipt. "
            "Ocean freight charges exceeding $10,000 per shipment require manager approval before allocation. "
            "All customs brokerage fees must include the customs entry number for audit trail purposes. "
            "Invoices without a valid vendor reference number must be flagged for review. "
            "Fuel surcharges should be allocated to the same project code as the primary freight charge. "
            "Terminal handling charges (THC) are allocated separately under port operations. "
            "Any invoice with more than 10 line items should be reviewed for potential consolidation opportunities. "
            "Currency conversion for non-USD invoices uses the exchange rate on the invoice date. "
            "Duplicate invoice detection: check invoice number and vendor combination before processing."
        ),
    },
    {
        "title": "SOP-002: Cost Center Assignment Guidelines",
        "content": (
            "Cost Center Assignment Guidelines for Logistics Operations. "
            "LOGISTICS-OPS: All transportation and freight charges including ocean, air, and ground transport. "
            "This includes fuel surcharges, drayage, and container shipping fees. "
            "COMPLIANCE: Customs clearance, brokerage fees, inspections, fumigation, and regulatory compliance charges. "
            "All government-imposed fees and duties fall under this cost center. "
            "WAREHOUSE: Storage fees, warehouse handling, distribution charges, and inventory management costs. "
            "Includes both owned and third-party warehouse charges. "
            "FINANCE: Insurance premiums, banking fees, letters of credit, and financial instrument charges. "
            "Cargo insurance and transit insurance are categorized here. "
            "ADMIN: Documentation fees, administrative charges, and overhead allocations. "
            "Includes courier fees for document handling and communication charges. "
            "When a charge spans multiple cost centers, allocate to the primary activity cost center. "
            "Quarterly review of cost center assignments is mandatory to ensure accuracy."
        ),
    },
    {
        "title": "SOP-003: GL Account Mapping for Logistics",
        "content": (
            "General Ledger Account Mapping for Logistics Expenses. "
            "5100-FREIGHT: All freight transportation charges — ocean freight, air freight, and ground transport. "
            "This is the primary account for carrier payments and shipping line invoices. "
            "5110-TRUCKING: Dedicated account for domestic trucking, drayage, and last-mile delivery. "
            "Separate from 5100 to track inland vs international freight costs. "
            "5120-DEMURRAGE: Demurrage and detention charges from ports and container yards. "
            "Used for tracking delays and efficiency metrics. "
            "5130-TERMINAL: Terminal handling charges (THC) at origin and destination ports. "
            "5200-CUSTOMS: Customs duties, brokerage fees, and clearance charges. "
            "All import/export regulatory costs are booked here. "
            "5210-INSPECTION: Fumigation, phytosanitary inspection, and compliance testing. "
            "5300-STORAGE: Warehousing and storage fees for both short-term and long-term storage. "
            "5400-INSURANCE: Cargo insurance, transit insurance, and related premiums. "
            "5500-ADMIN: Administrative fees, documentation charges, and miscellaneous overhead. "
            "The GL account mapping is reviewed annually and updated as needed. "
            "Any new charge types must be approved by the finance team before a new GL account is created."
        ),
    },
]


class RAGIngestor:
    """Ingests documents and SOPs into the vector store for RAG."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.embedding_service = EmbeddingService(settings)

    async def ingest_extraction(
        self,
        document_id: uuid.UUID,
        extraction: dict,
        doc_type: str,
        original_filename: str,
        db: AsyncSession,
    ) -> int:
        """Ingest an extraction result into the RAG vector store.

        Converts the structured extraction to natural language, chunks it,
        generates embeddings, and stores in pgvector.

        Returns the number of chunks ingested.
        """
        # Convert extraction to readable text
        text = extraction_to_text(extraction, doc_type)
        chunks = chunk_text(text)

        if not chunks:
            logger.warning("No chunks generated for document %s", document_id)
            return 0

        # Generate embeddings
        embeddings = await self.embedding_service.embed_texts(chunks)

        # Store in DB
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
            await db.execute(
                sa_text("""
                    INSERT INTO embeddings (id, document_id, content, source_type, source_id,
                                            chunk_index, metadata, embedding, created_at)
                    VALUES (:id, :doc_id, :content, :source_type, :source_id,
                            :chunk_index, CAST(:metadata AS json), CAST(:embedding AS vector), NOW())
                """),
                {
                    "id": uuid.uuid4(),
                    "doc_id": document_id,
                    "content": chunk,
                    "source_type": "extraction",
                    "source_id": document_id,
                    "chunk_index": i,
                    "metadata": json.dumps({
                        "title": original_filename,
                        "doc_type": doc_type,
                    }),
                    "embedding": vec_str,
                },
            )

        await db.flush()
        logger.info(
            "Ingested %d chunks for document %s (%s)", len(chunks), document_id, original_filename
        )
        return len(chunks)

    async def ingest_sample_sops(self, db: AsyncSession) -> int:
        """Seed the vector store with sample SOP documents for demo.

        Returns the total number of chunks ingested.
        """
        total_chunks = 0

        for sop in SAMPLE_SOPS:
            # Check if already ingested by looking for matching title in metadata
            existing = await db.execute(
                sa_text(
                    "SELECT COUNT(*) FROM embeddings "
                    "WHERE source_type = 'sop' AND metadata->>'title' = :title"
                ),
                {"title": sop["title"]},
            )
            if existing.scalar() > 0:
                logger.info("SOP '%s' already ingested, skipping", sop["title"])
                continue

            chunks = chunk_text(sop["content"])
            if not chunks:
                continue

            embeddings = await self.embedding_service.embed_texts(chunks)
            sop_id = uuid.uuid4()

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                await db.execute(
                    sa_text("""
                        INSERT INTO embeddings (id, document_id, content, source_type, source_id,
                                                chunk_index, metadata, embedding, created_at)
                        VALUES (:id, NULL, :content, :source_type, :source_id,
                                :chunk_index, CAST(:metadata AS json), CAST(:embedding AS vector), NOW())
                    """),
                    {
                        "id": uuid.uuid4(),
                        "doc_id": None,
                        "content": chunk,
                        "source_type": "sop",
                        "source_id": sop_id,
                        "chunk_index": i,
                        "metadata": json.dumps({"title": sop["title"]}),
                        "embedding": vec_str,
                    },
                )
                total_chunks += 1

        await db.flush()
        logger.info("Ingested %d SOP chunks total", total_chunks)
        return total_chunks
