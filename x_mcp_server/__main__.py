"""Console entry point: ``x-mcp-server`` / ``python -m x_mcp_server``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import shutil
import sys
from pathlib import Path

from .browser import get_session
from .config import get_settings
from .server import mcp
from .tools.auth import login

logger = logging.getLogger(__name__)


def _setup_logging(log_level: str = "INFO") -> None:
    """Set up logging for CLI commands."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def _login_interactive() -> bool:
    """Run the interactive login flow. The browser is always visible here (main()
    forces headless off for --login) so you can sign in and clear any challenge.

    Returns True on success. The browser is closed before returning so the
    Playwright/Chrome subprocesses shut down cleanly inside the event loop,
    instead of being killed abruptly at interpreter exit (which leaks terminal
    capability-probe replies onto the next shell prompt)."""
    _setup_logging("INFO")
    settings = get_settings()
    print("✓ Browser window will be visible for manual sign-in.")
    print(f"Opening X login page (timeout: {settings.login_timeout_ms / 1000:.0f}s)...")
    try:
        result = await login()
        print(f"{'✓' if result.ok else '✗'} {result.message}")
        return result.ok
    finally:
        await get_session().close()


async def _check_auth() -> bool:
    """Check if the current session is authenticated. Closes the browser before
    returning (see _login_interactive for why clean shutdown matters)."""
    _setup_logging("INFO")
    try:
        authenticated = await get_session().is_authenticated()
        if authenticated:
            print("✓ Session is authenticated.")
        else:
            print("✗ Session is NOT authenticated.")
            print("Run with --login to sign in, or set X_AUTH_TOKEN and X_CSRF_TOKEN.")
        return authenticated
    finally:
        await get_session().close()


def _logout() -> None:
    """Clear the saved browser profile."""
    settings = get_settings()
    profile_path = Path(settings.user_data_dir).expanduser()

    if profile_path.exists():
        print(f"Clearing browser profile at {profile_path}...")
        shutil.rmtree(profile_path)
        print("✓ Browser profile cleared.")
    else:
        print(f"No browser profile found at {profile_path}.")

    sys.exit(0)


def main() -> None:
    """CLI entry point with support for login, logout, and server modes."""
    parser = argparse.ArgumentParser(
        prog="x-mcp-server",
        description="X (Twitter) scraping MCP server powered by Patchright.",
    )

    parser.add_argument(
        "--login",
        action="store_true",
        help="Run interactive login (opens browser, saves session to profile).",
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Clear the saved browser profile and exit.",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Check if the current session is authenticated and exit.",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show the browser window (useful for debugging or login).",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO).",
    )

    args = parser.parse_args()

    # Force a visible browser for --login (you can't sign in to a headless one),
    # and honour --no-headless for any mode. Settings are a cached singleton that
    # was already populated at import time, so mutate the object directly rather
    # than os.environ, which would be read too late to have any effect.
    if args.login or args.no_headless:
        get_settings().headless = False

    if args.logout:
        _logout()
    elif args.check_auth:
        sys.exit(0 if asyncio.run(_check_auth()) else 1)
    elif args.login:
        sys.exit(0 if asyncio.run(_login_interactive()) else 1)
    else:
        _setup_logging(args.log_level)
        mcp.run()


if __name__ == "__main__":
    main()
