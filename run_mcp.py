#!/usr/bin/env python
"""Entry point for the persona MCP server."""
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.mcp_server import mcp

mcp.run(transport="stdio")
