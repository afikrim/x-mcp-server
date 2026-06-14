"""Write actions: post, reply, like, and follow.

These drive the X web UI through stable ``data-testid`` selectors instead of the
private GraphQL API, which keeps them consistent with the rest of the scraper and
avoids replicating X's request-signing (the ``x-client-transaction-id`` header).
The trade-off is that they depend on the compose/action DOM, the most volatile
part of the site. Every action requires an authenticated session; run ``login``
or supply ``X_AUTH_TOKEN`` first.

The equivalent reverse-engineered GraphQL calls (``CreateTweet``, etc.) are
documented in ``docs/RESEARCH.md`` for a future browserless implementation.
"""

from __future__ import annotations

import asyncio
import logging
import re

from ..browser import get_session
from ..exceptions import ActionError
from ..extract import extract_tweets, normalize_handle
from ..models import ActionResult

logger = logging.getLogger(__name__)

# Compose surface. Scope to the primary column: navigating to /compose/post
# overlays a modal on top of the home feed, so an unscoped tweetTextarea_0 matches
# *two* composers (the modal and the home inline box) and trips strict mode. We
# drive the home inline composer in primaryColumn instead — exactly one match, no
# overlay/focus-trap to fight. Its submit button is tweetButtonInline.
_PRIMARY = '[data-testid="primaryColumn"] '
_COMPOSE_BOX = f'{_PRIMARY}[data-testid="tweetTextarea_0"]'
_POST_BUTTON = f'{_PRIMARY}[data-testid="tweetButton"]'
_POST_BUTTON_INLINE = f'{_PRIMARY}[data-testid="tweetButtonInline"]'
_TOAST = '[data-testid="toast"]'

# Per-tweet action bar.
_REPLY_BUTTON = '[data-testid="reply"]'
_LIKE_BUTTON = '[data-testid="like"]'
_UNLIKE_BUTTON = '[data-testid="unlike"]'
# Follow buttons carry a data-testid like "<userId>-follow" / "<userId>-unfollow".
_FOLLOW_BUTTON = '[data-testid$="-follow"]'

_MAX_TWEET_LEN = 280


async def _type_into_compose(page, text: str) -> None:
    """Enter ``text`` into the Draft.js compose box via real keystrokes.

    The compose surface (``tweetTextarea_0``) is a contenteditable Draft.js
    editor that React renders from its own internal state. ``page.fill`` writes
    the DOM directly, which Draft never sees: its input handlers don't fire, the
    editor state stays empty, React reverts the node, and the Post button stays
    ``disabled``. Focusing then typing key-by-key drives Draft's real input
    pipeline so both the text and the button's enabled state update.
    """
    box = page.locator(_COMPOSE_BOX).first
    await box.click()
    await box.press_sequentially(text)


async def _click_when_enabled(page, *selectors: str):
    """Click the first present compose/post button, waiting until it's enabled.

    The button toggles from ``disabled``/``aria-disabled="true"`` to enabled once
    the editor has content. Playwright's actionability check waits out the real
    ``disabled`` attribute; we additionally guard ``aria-disabled`` for safety.
    """
    for selector in selectors:
        button = page.locator(selector).first
        if await button.count() == 0:
            continue
        try:
            await page.wait_for_selector(
                f"{selector}:not([aria-disabled='true'])", timeout=8_000
            )
        except Exception:  # noqa: BLE001 - fall through to click's own wait
            pass
        await button.click()
        return
    raise ActionError(f"No enabled post button found (tried: {', '.join(selectors)}).")


def _status_url(url_or_id: str) -> str:
    if url_or_id.startswith("http"):
        return url_or_id
    m = re.search(r"status/(\d+)", url_or_id)
    status_id = m.group(1) if m else url_or_id.strip()
    if not status_id.isdigit():
        raise ActionError(f"Could not find a status id in '{url_or_id}'")
    return f"https://x.com/i/status/{status_id}"


async def post_tweet(text: str) -> ActionResult:
    """Publish a new post (tweet) from the authenticated account.

    Args:
        text: The post body. Standard accounts are capped at 280 characters.

    Returns:
        ActionResult with ``ok`` true and the new post's URL/id when resolvable.
    """
    if not text.strip():
        raise ActionError("Cannot post an empty tweet.")
    if len(text) > _MAX_TWEET_LEN:
        raise ActionError(f"Tweet exceeds {_MAX_TWEET_LEN} characters ({len(text)}).")

    session = get_session()
    page = await session.new_page()
    try:
        # Use the home inline composer rather than /compose/post (which opens a
        # modal over the feed and produces a duplicate tweetTextarea_0).
        await session.goto(
            page,
            "https://x.com/home",
            wait_for=_COMPOSE_BOX,
        )
        await _type_into_compose(page, text)
        await _click_when_enabled(page, _POST_BUTTON, _POST_BUTTON_INLINE)

        url, status_id = await _wait_for_new_post(page)
        return ActionResult(
            ok=True,
            action="post_tweet",
            message="Posted.",
            url=url,
            id=status_id,
        )
    finally:
        await page.close()


async def reply_to_tweet(url_or_id: str, text: str) -> ActionResult:
    """Reply to an existing post.

    Args:
        url_or_id: A full post URL or the bare numeric status id to reply to.
        text: The reply body (max 280 characters on standard accounts).

    Returns:
        ActionResult describing the posted reply.
    """
    if not text.strip():
        raise ActionError("Cannot post an empty reply.")
    if len(text) > _MAX_TWEET_LEN:
        raise ActionError(f"Reply exceeds {_MAX_TWEET_LEN} characters ({len(text)}).")

    url = _status_url(url_or_id)
    session = get_session()
    page = await session.new_page()
    try:
        await session.goto(page, url, wait_for=_REPLY_BUTTON)
        # The inline reply box on a status page is the compose textarea.
        await _type_into_compose(page, text)
        await _click_when_enabled(page, _POST_BUTTON_INLINE, _POST_BUTTON)

        new_url, status_id = await _wait_for_new_post(page)
        return ActionResult(
            ok=True,
            action="reply_to_tweet",
            message=f"Replied to {url}.",
            url=new_url,
            id=status_id,
        )
    finally:
        await page.close()


async def like_tweet(url_or_id: str) -> ActionResult:
    """Like a post by URL or status id (no-op if already liked).

    Args:
        url_or_id: A full post URL or the bare numeric status id.
    """
    url = _status_url(url_or_id)
    session = get_session()
    page = await session.new_page()
    try:
        await session.goto(page, url, wait_for='article[data-testid="tweet"]')
        if await page.locator(_UNLIKE_BUTTON).count() > 0:
            return ActionResult(ok=True, action="like_tweet", message="Already liked.", url=url)
        await page.locator(_LIKE_BUTTON).first.click()
        await page.wait_for_selector(_UNLIKE_BUTTON, timeout=8_000)
        return ActionResult(ok=True, action="like_tweet", message="Liked.", url=url)
    finally:
        await page.close()


async def follow_user(username: str) -> ActionResult:
    """Follow a user from their profile page.

    Args:
        username: An @handle, plain handle, or full profile URL.
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
        follow = page.locator(_FOLLOW_BUTTON)
        if await follow.count() == 0:
            return ActionResult(
                ok=True,
                action="follow_user",
                message=f"Already following @{handle} (or no follow button shown).",
            )
        await follow.first.click()
        return ActionResult(ok=True, action="follow_user", message=f"Followed @{handle}.")
    finally:
        await page.close()


async def _wait_for_new_post(page) -> tuple[str | None, str | None]:
    """After submitting, wait for the compose UI to settle and resolve the new post.

    Best-effort: X navigates to the new status or shows a confirmation toast. We
    give it a moment, then read back the freshest tweet on the page for its URL/id.
    """
    try:
        await page.wait_for_selector(_TOAST, timeout=8_000)
    except Exception:  # noqa: BLE001
        await asyncio.sleep(2.0)

    try:
        tweets = await extract_tweets(page, limit=1)
        if tweets:
            return tweets[0].url, tweets[0].id
    except Exception:  # noqa: BLE001
        pass
    return None, None
