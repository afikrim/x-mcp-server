"""Tool registration for the X MCP server.

Each tool is a plain async function elsewhere in this package; ``register`` wires
them onto a FastMCP instance so the implementation stays decoupled from the
server wiring.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .auth import login, login_with_credentials
from .post import follow_user, like_tweet, post_tweet, reply_to_tweet
from .profile import get_profile
from .search import search_tweets
from .timeline import get_tweet, get_user_tweets


def register(mcp: FastMCP) -> None:
    """Attach all read and write tools to ``mcp``."""
    # Read / scrape
    mcp.tool(get_profile)
    mcp.tool(get_user_tweets)
    mcp.tool(get_tweet)
    mcp.tool(search_tweets)
    # Auth
    mcp.tool(login)
    mcp.tool(login_with_credentials)
    # Write
    mcp.tool(post_tweet)
    mcp.tool(reply_to_tweet)
    mcp.tool(like_tweet)
    mcp.tool(follow_user)


__all__ = [
    "register",
    "get_profile",
    "get_user_tweets",
    "get_tweet",
    "search_tweets",
    "login",
    "login_with_credentials",
    "post_tweet",
    "reply_to_tweet",
    "like_tweet",
    "follow_user",
]
