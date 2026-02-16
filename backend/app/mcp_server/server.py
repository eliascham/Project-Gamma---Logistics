"""LogisticsMCPServer — MCP server using official Python SDK.

Exposes 4 tools for logistics data queries:
- query_freight_lanes: Search freight shipment data
- get_warehouse_inventory: Query warehouse inventory levels
- lookup_project_budget: Look up project budget utilization
- search_purchase_orders: Search purchase orders

Runs over stdio for Claude Desktop integration.
"""

import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from app.mcp_server.data_layer import MCPDataLayer

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
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2, default=str),
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    return server


async def run_server(database_url: str | None = None):
    """Run the MCP server over stdio."""
    server = create_server(database_url)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
