"""Manual smoke test for the compose flow. POSTS to the logged-in account.

Runs the browser visibly so you can watch the type + click happen. Requires a
prior `uv run mcp-server-x --login` (the session is read from X_USER_DATA_DIR).

Usage:
    uv run python scripts/post_test.py "hello from x-mcp-server"
"""

from __future__ import annotations

import asyncio
import logging
import sys

from x_mcp_server.browser import get_session
from x_mcp_server.config import get_settings
from x_mcp_server.tools.post import post_tweet


async def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Usage: uv run python scripts/post_test.py "your tweet text"')
        raise SystemExit(1)

    text = sys.argv[1]
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Watch it run instead of headless. Mutate the cached singleton (env is read
    # too late once config is imported).
    get_settings().headless = False

    try:
        result = await post_tweet(text)
        print("\nResult:", result.model_dump())
    finally:
        await get_session().close()


if __name__ == "__main__":
    asyncio.run(main())
