"""FastMCP server definition for x-mcp-server."""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from .browser import get_session
from .config import get_settings
from .tools import register

logger = logging.getLogger(__name__)


def build_server() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    mcp = FastMCP(
        name="x-mcp-server",
        instructions=(
            "Scrapes public content from X (formerly Twitter) using a stealth "
            "browser. Use get_profile for user details, get_user_tweets for a "
            "user's recent posts, get_tweet for a single post, and search_tweets "
            "to query across X. Handles may be passed as '@name', 'name', or a "
            "full profile URL."
        ),
    )

    register(mcp)

    @mcp.tool
    async def check_auth() -> dict:
        """Report whether the browser session is logged in to X.

        Returns a dict with 'authenticated' (bool) and 'has_session_cookies'
        (whether X_AUTH_TOKEN was supplied). Use this to diagnose empty results.
        """
        session = get_session()
        return {
            "authenticated": await session.is_authenticated(),
            "has_session_cookies": get_settings().has_session_cookies,
        }

    return mcp


mcp = build_server()
