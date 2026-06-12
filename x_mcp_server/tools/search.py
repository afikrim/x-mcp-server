"""Search tools."""

from __future__ import annotations

from urllib.parse import quote

from ..browser import get_session
from ..models import Tweet
from ._common import collect_tweets


async def search_tweets(query: str, limit: int = 20, latest: bool = True) -> list[Tweet]:
    """Search X for posts matching a query.

    Args:
        query: A search query. Supports X's search operators (e.g.
            'from:jack', '#python', '"exact phrase"', 'min_faves:100').
        limit: Maximum number of posts to return (1-100).
        latest: If true, use the "Latest" tab (chronological); otherwise "Top".

    Returns:
        Matching posts with text, author, timestamp, and engagement counts.
    """
    limit = max(1, min(limit, 100))
    tab = "live" if latest else "top"
    url = f"https://x.com/search?q={quote(query)}&src=typed_query&f={tab}"

    session = get_session()
    page = await session.new_page()
    try:
        await session.goto(page, url, wait_for='article[data-testid="tweet"]')
        return await collect_tweets(page, limit)
    finally:
        await page.close()
