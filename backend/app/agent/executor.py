"""Tool executor — bridges agent tool calls to real backend services.

Each method corresponds to a tool in tools.py and calls the appropriate
service layer function. The executor owns DB sessions and service instances.
"""

import json
import logging
from dataclasses import asdict

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.mcp_server.data_layer import MCPDataLayer
from app.reconciliation_engine.invoice_reconciler import reconcile_invoice
from app.schemas.extraction import DocumentType
from app.validator.service import ValidationService

logger = logging.getLogger("gamma.agent.executor")


class ToolExecutor:
    """Executes agent tool calls against real backend services."""

    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.data_layer = MCPDataLayer(database_url=str(settings.database_url))

    async def execute(self, tool_name: str, tool_input: dict) -> dict:
        """Dispatch a tool call to the appropriate handler.

        Returns a dict with the tool result (always JSON-serializable).
        """
        handler = getattr(self, f"_handle_{tool_name}", None)
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return await handler(tool_input)
        except Exception as e:
            logger.exception("Tool %s failed", tool_name)
            return {"error": str(e)}

    async def _handle_extract_document(self, args: dict) -> dict:
        """Run extraction pipeline on a document."""
        from app.document_extractor.pipeline import ExtractionPipeline

        document_id = args["document_id"]

        # Fetch document info
        doc = await self.data_layer.get_document(document_id)
        if doc is None:
            return {"error": f"Document {document_id} not found"}

        if doc["status"] != "uploaded":
            # Check if already extracted
            existing = await self.data_layer.get_extraction(document_id)
            if existing:
                return {
                    "status": "already_extracted",
                    "extraction": existing,
                }

        # Build file path
        file_path = f"{self.settings.upload_dir}/{document_id}/{doc['filename']}"

        pipeline = ExtractionPipeline(self.settings)
        force_type = None
        if args.get("force_doc_type"):
            force_type = DocumentType(args["force_doc_type"])

        result = await pipeline.run(
            file_path=file_path,
            file_type=doc["file_type"],
            mime_type=doc["mime_type"],
            force_doc_type=force_type,
        )

        return {
            "status": "extracted",
            "document_type": result.document_type.value,
            "extraction": result.refined_extraction,
            "field_confidences": result.field_confidences,
            "overall_confidence": result.overall_confidence,
            "validation_passed": result.validation.passed if result.validation else None,
            "validation_errors": result.validation.error_count if result.validation else 0,
            "validation_issues": [
                {
                    "field": i.field,
                    "severity": i.severity.value,
                    "message": i.message,
                    "rule": i.rule,
                }
                for i in (result.validation.issues if result.validation else [])
            ],
            "processing_time_ms": result.processing_time_ms,
        }

    async def _handle_validate_extraction(self, args: dict) -> dict:
        """Run deterministic validation on an extraction."""
        doc_type = DocumentType(args["document_type"])
        result = ValidationService.validate(args["extraction"], doc_type)
        return {
            "passed": result.passed,
            "error_count": result.error_count,
            "warning_count": result.warning_count,
            "issues": [
                {
                    "field": i.field,
                    "severity": i.severity.value,
                    "message": i.message,
                    "rule": i.rule,
                    "expected": i.expected,
                    "actual": i.actual,
                }
                for i in result.issues
            ],
        }

    async def _handle_search_shipments(self, args: dict) -> dict:
        """Search shipments for reconciliation."""
        shipments = await self.data_layer.search_shipments_for_reconciliation(
            vendor=args.get("vendor"),
            po_number=args.get("po_number"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
            limit=args.get("limit", 50),
        )
        return {"shipments": shipments, "count": len(shipments)}

    async def _handle_reconcile_invoice(self, args: dict) -> dict:
        """Reconcile an invoice against shipments."""
        invoice_extraction = args.get("invoice_extraction")
        shipments = args.get("shipments")

        # Auto-fetch extraction if document_id provided
        if args.get("document_id") and not invoice_extraction:
            ext = await self.data_layer.get_extraction(args["document_id"])
            if ext is None:
                return {"error": "No extraction found for this document"}
            invoice_extraction = ext.get("extraction", ext)

        if not invoice_extraction:
            return {"error": "Either document_id or invoice_extraction is required"}

        # Auto-search shipments if not provided
        if not shipments:
            vendor = (
                invoice_extraction.get("vendor_name")
                or invoice_extraction.get("carrier")
            )
            shipments = await self.data_layer.search_shipments_for_reconciliation(
                vendor=vendor,
                po_number=invoice_extraction.get("po_number"),
            )

        result = reconcile_invoice(
            invoice_extraction,
            shipments,
            top_n=args.get("top_n", 3),
        )

        # Serialize
        from app.mcp_server.server import _reconciliation_result_to_dict
        return _reconciliation_result_to_dict(result)

    async def _handle_create_review_item(self, args: dict) -> dict:
        """Create a HITL review queue item."""
        metadata = args.get("metadata", {})
        metadata_json = json.dumps(metadata) if metadata else "{}"

        query = sa_text(
            "INSERT INTO review_queue (status, item_type, title, description, "
            "severity, dollar_amount, metadata) "
            "VALUES ('pending', :item_type, :title, :description, "
            ":severity, :dollar_amount, :metadata) "
            "RETURNING id"
        )
        result = await self.session.execute(query, {
            "item_type": args["item_type"],
            "title": args["title"],
            "description": args["description"],
            "severity": args["severity"],
            "dollar_amount": args.get("dollar_amount"),
            "metadata": metadata_json,
        })
        await self.session.commit()
        row = result.first()
        return {
            "status": "created",
            "review_item_id": str(row[0]) if row else None,
            "title": args["title"],
            "severity": args["severity"],
        }

    async def _handle_log_audit_event(self, args: dict) -> dict:
        """Log an audit event."""
        from app.audit_generator.service import AuditService
        import uuid as _uuid

        entity_id = args["entity_id"]
        try:
            entity_uuid = _uuid.UUID(entity_id)
        except (ValueError, AttributeError):
            entity_uuid = None

        await AuditService.log_event(
            self.session,
            event_type=args["action"],
            entity_type=args["entity_type"],
            entity_id=entity_uuid,
            action=args["action"],
            actor="agent",
            actor_type="agent",
            new_state=args.get("details", {}),
        )
        return {"status": "logged", "action": args["action"]}

    async def _handle_get_document_info(self, args: dict) -> dict:
        """Get document metadata."""
        doc = await self.data_layer.get_document(args["document_id"])
        if doc is None:
            return {"error": "Document not found"}
        return doc

    async def _handle_get_extraction(self, args: dict) -> dict:
        """Get existing extraction for a document."""
        ext = await self.data_layer.get_extraction(args["document_id"])
        if ext is None:
            return {"error": "No extraction found"}
        return ext

    async def close(self):
        """Cleanup resources."""
        await self.data_layer.close()
