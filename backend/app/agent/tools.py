"""Agent tool definitions for Claude tool_use orchestration.

Each tool maps to an existing backend capability (extraction, validation,
reconciliation, HITL queue, audit). The agent picks which tools to call
and in what order based on the user's goal.
"""

# Tool definitions in Anthropic tool_use format
AGENT_TOOLS = [
    {
        "name": "extract_document",
        "description": (
            "Run the extraction pipeline on a document. Parses the file, "
            "classifies the document type, runs 2-pass extraction with Claude, "
            "computes per-field confidence, and runs deterministic validation. "
            "Returns the structured extraction with confidence scores and validation results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "UUID of the document to extract",
                },
                "force_doc_type": {
                    "type": "string",
                    "description": "Optional: force a specific document type (e.g., 'freight_invoice', 'bill_of_lading')",
                },
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "validate_extraction",
        "description": (
            "Run deterministic validation on an extraction result. "
            "Checks required fields, line item math, totals, dates, currency, "
            "amounts, and reference number formats. Returns validation issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "extraction": {
                    "type": "object",
                    "description": "The extraction dict to validate",
                },
                "document_type": {
                    "type": "string",
                    "description": "Document type (e.g., 'freight_invoice')",
                },
            },
            "required": ["extraction", "document_type"],
        },
    },
    {
        "name": "search_shipments",
        "description": (
            "Search for shipment records that might match an invoice. "
            "Returns shipments with reference numbers, carriers, amounts, and dates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor": {"type": "string", "description": "Filter by carrier/vendor name"},
                "po_number": {"type": "string", "description": "Filter by PO number"},
                "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "limit": {"type": "integer", "description": "Max results (default 50)"},
            },
        },
    },
    {
        "name": "reconcile_invoice",
        "description": (
            "Match an extracted invoice against a list of shipments. "
            "Returns ranked candidates with match scores, reasons, and field-level diffs. "
            "If shipments are not provided, searches automatically based on the invoice's "
            "vendor and PO number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "UUID of the invoice document (auto-fetches extraction)",
                },
                "invoice_extraction": {
                    "type": "object",
                    "description": "Invoice extraction dict (alternative to document_id)",
                },
                "shipments": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Shipment records to match against (optional — auto-searched if omitted)",
                },
                "top_n": {"type": "integer", "description": "Number of top candidates (default 3)"},
            },
        },
    },
    {
        "name": "create_review_item",
        "description": (
            "Create a human-in-the-loop review item. Use this when reconciliation "
            "requires manual review (multiple close candidates, no strong match, "
            "or validation failures)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the review item"},
                "description": {
                    "type": "string",
                    "description": "Detailed description including context and what needs review",
                },
                "item_type": {
                    "type": "string",
                    "enum": ["reconciliation_mismatch", "low_confidence", "validation_failure", "exception"],
                    "description": "Type of review item",
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Severity level",
                },
                "dollar_amount": {"type": "number", "description": "Dollar amount involved"},
                "metadata": {
                    "type": "object",
                    "description": "Additional context (document_id, candidates, diffs, etc.)",
                },
            },
            "required": ["title", "description", "item_type", "severity"],
        },
    },
    {
        "name": "log_audit_event",
        "description": (
            "Log an audit event for traceability. Records who did what, when, "
            "and with what result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action performed (e.g., 'extraction_completed', 'reconciliation_matched', 'review_created')",
                },
                "entity_type": {
                    "type": "string",
                    "description": "Entity type (e.g., 'document', 'invoice', 'reconciliation')",
                },
                "entity_id": {"type": "string", "description": "ID of the entity"},
                "details": {"type": "object", "description": "Additional details about the action"},
            },
            "required": ["action", "entity_type", "entity_id"],
        },
    },
    {
        "name": "get_document_info",
        "description": (
            "Get metadata about a document: filename, file type, status, page count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "UUID of the document"},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "get_extraction",
        "description": (
            "Get the existing extraction result for a document (if already extracted)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "UUID of the document"},
            },
            "required": ["document_id"],
        },
    },
]
