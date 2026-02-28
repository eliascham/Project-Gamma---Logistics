"""Entry point for running the MCP server as a module.

Usage:
    python -m app.mcp_server              # stdio (Claude Desktop)
    python -m app.mcp_server --sse        # HTTP/SSE transport

Claude Desktop config:
    {
        "mcpServers": {
            "project-gamma": {
                "command": "python",
                "args": ["-m", "app.mcp_server"],
                "cwd": "/path/to/backend"
            }
        }
    }
"""

import asyncio
import sys

from app.mcp_server.server import run_server

if __name__ == "__main__":
    transport = "sse" if "--sse" in sys.argv else "stdio"
    asyncio.run(run_server(transport=transport))
