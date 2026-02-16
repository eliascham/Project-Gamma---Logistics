"""Entry point for running the MCP server as a module.

Usage:
    python -m app.mcp_server

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

from app.mcp_server.server import run_server

if __name__ == "__main__":
    asyncio.run(run_server())
