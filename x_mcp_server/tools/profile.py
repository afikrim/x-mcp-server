"""Profile-related tools."""

from __future__ import annotations

from ..browser import get_session
from ..extract import extract_profile, normalize_handle
from ..models import Profile


async def get_profile(username: str) -> Profile:
    """Fetch a user's public profile on X.

    Args:
        username: An @handle, plain handle, or full profile URL (e.g. "@jack",
            "jack", or "https://x.com/jack").

    Returns:
        The user's display name, bio, location, website, join date, and
        follower/following counts.
    """
    handle = normalize_handle(username)
    session = get_session()
    page = await session.new_page()
    try:
        await session.goto(
            page,
            f"https://x.com/{handle}",
            wait_for='[data-testid="UserName"]',
        )
        return await extract_profile(page, handle)
    finally:
        await page.close()
