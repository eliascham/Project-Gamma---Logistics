"""Sub-agent definitions — specialized tool subsets + system prompts.

Each sub-agent gets a narrow tool set and focused system prompt.
The main orchestrator can delegate sub-tasks to these agents.
"""

from app.agent.tools import AGENT_TOOLS


def _tools_by_names(names: list[str]) -> list[dict]:
    """Filter AGENT_TOOLS to only include the named tools."""
    name_set = set(names)
    return [t for t in AGENT_TOOLS if t["name"] in name_set]


# ─── Extraction Agent ───────────────────────────────────────────

EXTRACTION_AGENT_SYSTEM = """You are a document extraction specialist. Your job is to:
1. Look up a document's info to understand its type and format
2. Run extraction to pull structured data from the document
3. Validate the extraction for accuracy
4. Report the results with confidence scores

Focus on extraction quality. Flag any fields with low confidence."""

EXTRACTION_AGENT_TOOLS = _tools_by_names([
    "get_document_info",
    "extract_document",
    "validate_extraction",
    "get_extraction",
    "log_audit_event",
])


# ─── Reconciliation Agent ───────────────────────────────────────

RECONCILIATION_AGENT_SYSTEM = """You are an invoice reconciliation specialist. Your job is to:
1. Get the extraction data for an invoice
2. Search for candidate shipments by vendor and PO number
3. Run reconciliation to find the best matching shipment
4. If auto_match is True, report the match
5. If no auto-match, create a review item for human review

Be precise about match scores and explain why matches succeed or fail."""

RECONCILIATION_AGENT_TOOLS = _tools_by_names([
    "get_extraction",
    "search_shipments",
    "reconcile_invoice",
    "create_review_item",
    "log_audit_event",
])


# ─── Audit Agent ────────────────────────────────────────────────

AUDIT_AGENT_SYSTEM = """You are an audit and compliance specialist. Your job is to:
1. Review document and extraction details
2. Log audit events for all actions taken
3. Create review items when compliance issues are found
4. Ensure traceability of all processing steps

Focus on completeness and accuracy of the audit trail."""

AUDIT_AGENT_TOOLS = _tools_by_names([
    "get_document_info",
    "get_extraction",
    "create_review_item",
    "log_audit_event",
])


# ─── Registry ───────────────────────────────────────────────────

SUB_AGENT_REGISTRY = {
    "extraction": {
        "system_prompt": EXTRACTION_AGENT_SYSTEM,
        "tools": EXTRACTION_AGENT_TOOLS,
        "description": "Extract and validate documents",
    },
    "reconciliation": {
        "system_prompt": RECONCILIATION_AGENT_SYSTEM,
        "tools": RECONCILIATION_AGENT_TOOLS,
        "description": "Match invoices to shipments",
    },
    "audit": {
        "system_prompt": AUDIT_AGENT_SYSTEM,
        "tools": AUDIT_AGENT_TOOLS,
        "description": "Audit trail and compliance checks",
    },
}
