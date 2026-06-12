"""Tool registration for the X MCP server.

Each tool is a plain async function elsewhere in this package; ``register`` wires
them onto a FastMCP instance so the implementation stays decoupled from the
server wiring.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .profile import get_profile
from .search import search_tweets
from .timeline import get_tweet, get_user_tweets


def register(mcp: FastMCP) -> None:
    """Attach all scraping tools to ``mcp``."""
    mcp.tool(get_profile)
    mcp.tool(get_user_tweets)
    mcp.tool(get_tweet)
    mcp.tool(search_tweets)


__all__ = [
    "register",
    "get_profile",
    "get_user_tweets",
    "get_tweet",
    "search_tweets",
]
