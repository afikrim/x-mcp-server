"""Console entry point: ``x-mcp-server`` / ``python -m x_mcp_server``."""

from __future__ import annotations

from .server import mcp


def main() -> None:
    """Run the MCP server over stdio (the transport MCP clients expect)."""
    mcp.run()


if __name__ == "__main__":
    main()
