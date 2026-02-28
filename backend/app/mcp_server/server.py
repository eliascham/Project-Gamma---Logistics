"""LogisticsMCPServer — MCP server using official Python SDK.

Exposes 9 tools for logistics data queries and invoice processing:
- query_freight_lanes: Search freight shipment data
- get_warehouse_inventory: Query warehouse inventory levels
- lookup_project_budget: Look up project budget utilization
- search_purchase_orders: Search purchase orders
- get_document_details: Look up a document by ID
- get_extraction_result: Get extraction data for a document
- search_shipments: Search shipments for reconciliation
- reconcile_invoice: Match invoice extraction against shipments
- list_review_queue: List HITL review items

Supports both stdio (Claude Desktop) and SSE (HTTP) transport.
"""

import json
import logging
from dataclasses import asdict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from app.mcp_server.data_layer import MCPDataLayer
from app.reconciliation_engine.invoice_reconciler import reconcile_invoice

logger = logging.getLogger("gamma.mcp_server")

# Tool definitions
TOOLS = [
    Tool(
        name="query_freight_lanes",
        description=(
            "Search freight shipment data by origin, destination, or carrier. "
            "Returns shipment details including BOL numbers, amounts, status, and project codes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Filter by origin city/port (e.g., 'Shanghai')"},
                "destination": {"type": "string", "description": "Filter by destination city/port (e.g., 'Los Angeles')"},
                "carrier": {"type": "string", "description": "Filter by carrier name (e.g., 'Maersk')"},
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
            },
        },
    ),
    Tool(
        name="get_warehouse_inventory",
        description=(
            "Query warehouse inventory levels across facilities. "
            "Returns stock on hand, reserved quantities, unit costs, and reorder points."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "warehouse_code": {"type": "string", "description": "Filter by warehouse (WH-LAX, WH-CHI, WH-NYC)"},
                "sku": {"type": "string", "description": "Filter by SKU code (e.g., 'ELEC-001')"},
                "limit": {"type": "integer", "description": "Max results (default 50)", "default": 50},
            },
        },
    ),
    Tool(
        name="lookup_project_budget",
        description=(
            "Look up project budget information including budget amount, spent amount, "
            "remaining budget, and utilization percentage."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_code": {
                    "type": "string",
                    "description": "Project code (e.g., 'INTL-FREIGHT-001'). Omit to list all.",
                },
            },
        },
    ),
    Tool(
        name="search_purchase_orders",
        description=(
            "Search purchase orders by PO number, vendor, or status. "
            "Returns order details with line items."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "po_number": {"type": "string", "description": "Filter by PO number"},
                "vendor": {"type": "string", "description": "Filter by vendor name"},
                "status": {"type": "string", "description": "Filter by status (open, partially_received, received, closed)"},
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
            },
        },
    ),
    # --- Invoice Processing Tools ---
    Tool(
        name="get_document_details",
        description=(
            "Look up a document by its ID. Returns filename, file type, MIME type, "
            "processing status, document type, page count, and creation date."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "UUID of the document"},
            },
            "required": ["document_id"],
        },
    ),
    Tool(
        name="get_extraction_result",
        description=(
            "Get the latest extraction result for a document. Returns the structured "
            "extraction data, document type, model used, processing time, and metadata."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "UUID of the document"},
            },
            "required": ["document_id"],
        },
    ),
    Tool(
        name="search_shipments",
        description=(
            "Search shipment records for invoice reconciliation. "
            "Returns shipments with reference numbers, carriers, amounts, and dates. "
            "Use this to find candidate shipments before running reconcile_invoice."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "vendor": {"type": "string", "description": "Filter by carrier/vendor name"},
                "po_number": {"type": "string", "description": "Filter by PO number"},
                "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "limit": {"type": "integer", "description": "Max results (default 50)", "default": 50},
            },
        },
    ),
    Tool(
        name="reconcile_invoice",
        description=(
            "Match an extracted invoice against a pool of shipment records. "
            "Returns ranked candidates with match scores, reasons, and field-level diffs. "
            "Use search_shipments first to get candidate shipments, or provide a document_id "
            "to auto-fetch extraction and search shipments."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "UUID of the invoice document. If provided, extraction and shipments are fetched automatically.",
                },
                "invoice_extraction": {
                    "type": "object",
                    "description": "Invoice extraction dict (alternative to document_id). Must include fields like invoice_number, vendor_name, total_amount.",
                },
                "shipments": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of shipment records to match against (alternative to auto-search).",
                },
                "top_n": {"type": "integer", "description": "Number of top candidates to return (default 3)", "default": 3},
            },
        },
    ),
    Tool(
        name="list_review_queue",
        description=(
            "List items in the human-in-the-loop review queue. "
            "Returns review items with status, type, title, severity, and dollar amount."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status (pending, approved, rejected, escalated)",
                },
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
            },
        },
    ),
]


def create_server(database_url: str | None = None) -> Server:
    """Create and configure the MCP server."""
    server = Server("project-gamma-logistics")
    data_layer = MCPDataLayer(database_url=database_url)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            if name == "query_freight_lanes":
                results = await data_layer.query_freight_lanes(
                    origin=arguments.get("origin"),
                    destination=arguments.get("destination"),
                    carrier=arguments.get("carrier"),
                    limit=arguments.get("limit", 20),
                )
            elif name == "get_warehouse_inventory":
                results = await data_layer.get_warehouse_inventory(
                    warehouse_code=arguments.get("warehouse_code"),
                    sku=arguments.get("sku"),
                    limit=arguments.get("limit", 50),
                )
            elif name == "lookup_project_budget":
                results = await data_layer.lookup_project_budget(
                    project_code=arguments.get("project_code"),
                )
            elif name == "search_purchase_orders":
                results = await data_layer.search_purchase_orders(
                    po_number=arguments.get("po_number"),
                    vendor=arguments.get("vendor"),
                    status=arguments.get("status"),
                    limit=arguments.get("limit", 20),
                )

            # --- Invoice Processing Tools ---

            elif name == "get_document_details":
                doc = await data_layer.get_document(arguments["document_id"])
                if doc is None:
                    return [TextContent(type="text", text="Document not found")]
                results = doc

            elif name == "get_extraction_result":
                ext = await data_layer.get_extraction(arguments["document_id"])
                if ext is None:
                    return [TextContent(type="text", text="No extraction found for this document")]
                results = ext

            elif name == "search_shipments":
                results = await data_layer.search_shipments_for_reconciliation(
                    vendor=arguments.get("vendor"),
                    po_number=arguments.get("po_number"),
                    date_from=arguments.get("date_from"),
                    date_to=arguments.get("date_to"),
                    limit=arguments.get("limit", 50),
                )

            elif name == "reconcile_invoice":
                results = await _handle_reconcile(data_layer, arguments)

            elif name == "list_review_queue":
                results = await data_layer.list_review_items(
                    status=arguments.get("status"),
                    limit=arguments.get("limit", 20),
                )

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2, default=str),
            )]
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return [TextContent(type="text", text=f"Error: {e}")]

    return server


async def _handle_reconcile(data_layer: MCPDataLayer, arguments: dict) -> dict:
    """Handle the reconcile_invoice tool — fetch data if needed, run reconciliation."""
    invoice_extraction = arguments.get("invoice_extraction")
    shipments = arguments.get("shipments")

    # If document_id provided, fetch extraction and auto-search shipments
    if arguments.get("document_id") and not invoice_extraction:
        ext = await data_layer.get_extraction(arguments["document_id"])
        if ext is None:
            return {"error": "No extraction found for this document"}
        invoice_extraction = ext.get("extraction", ext)

    if not invoice_extraction:
        return {"error": "Either document_id or invoice_extraction is required"}

    # If no shipments provided, search for candidates
    if not shipments:
        vendor = (
            invoice_extraction.get("vendor_name")
            or invoice_extraction.get("carrier")
        )
        shipments = await data_layer.search_shipments_for_reconciliation(
            vendor=vendor,
            po_number=invoice_extraction.get("po_number"),
        )

    # Run reconciliation
    result = reconcile_invoice(
        invoice_extraction,
        shipments,
        top_n=arguments.get("top_n", 3),
    )

    # Serialize dataclass result to dict
    return _reconciliation_result_to_dict(result)


def _reconciliation_result_to_dict(result) -> dict:
    """Convert InvoiceReconciliationResult to a JSON-serializable dict."""
    candidates = []
    for c in result.candidates:
        diffs = [asdict(d) for d in c.diffs]
        candidates.append({
            "shipment_id": c.shipment_id,
            "shipment_ref": c.shipment_ref,
            "match_score": c.match_score,
            "status": c.status.value,
            "match_reasons": c.match_reasons,
            "diffs": diffs,
            "has_diffs": c.has_diffs,
        })
    best = None
    if result.best_match:
        best = {
            "shipment_id": result.best_match.shipment_id,
            "match_score": result.best_match.match_score,
            "status": result.best_match.status.value,
        }
    return {
        "invoice_number": result.invoice_number,
        "invoice_vendor": result.invoice_vendor,
        "invoice_total": result.invoice_total,
        "candidate_count": result.candidate_count,
        "candidates": candidates,
        "best_match": best,
        "auto_match": result.auto_match,
        "has_match": result.has_match,
        "exceptions": result.exceptions,
    }


async def run_server(database_url: str | None = None, transport: str = "stdio"):
    """Run the MCP server.

    Args:
        database_url: Override database URL (default: from settings).
        transport: Transport type — "stdio" for Claude Desktop, "sse" for HTTP.
    """
    server = create_server(database_url)

    if transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route
        import uvicorn

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await server.run(
                    streams[0], streams[1], server.create_initialization_options()
                )

        starlette_app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        port = int(__import__("os").environ.get("MCP_SERVER_PORT", "3001"))
        logger.info("Starting MCP SSE server on port %d", port)
        config = uvicorn.Config(starlette_app, host="0.0.0.0", port=port)
        srv = uvicorn.Server(config)
        await srv.serve()
    else:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
