"""Domain exceptions for the X MCP server."""

from __future__ import annotations


class XMCPError(Exception):
    """Base class for all errors raised by this server."""


class AuthenticationError(XMCPError):
    """Raised when the session is missing or no longer valid for X."""


class NavigationError(XMCPError):
    """Raised when a page fails to load or times out."""


class ParseError(XMCPError):
    """Raised when expected content could not be extracted from the page."""


class RateLimitError(XMCPError):
    """Raised when X signals that requests are being throttled."""
