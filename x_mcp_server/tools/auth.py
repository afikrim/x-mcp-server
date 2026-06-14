"""Authentication tools: interactive and (best-effort) automated sign-in.

X requires a logged-in session for nearly all content and every write action.
Two paths are exposed:

* ``login`` opens a visible browser to the X login screen and waits for a human
  to finish signing in (recommended; survives 2FA, email challenges, and the
  anti-bot transaction-id checks). The persistent Patchright profile then keeps
  the session warm across restarts.
* ``login_with_credentials`` is a fragile DOM-driven fallback that types the
  configured ``X_USERNAME`` / ``X_PASSWORD`` into the login form. It breaks on
  any interstitial challenge and is provided only as a convenience for headless,
  challenge-free accounts.

The reverse-engineered HTTP login flow (``/1.1/onboarding/task.json`` subtask
chain) is documented in ``docs/RESEARCH.md`` as the future, browserless path.
"""

from __future__ import annotations

import asyncio
import logging

from ..browser import get_session
from ..config import get_settings
from ..models import ActionResult

logger = logging.getLogger(__name__)

# Login form selectors. These live on the SSO/onboarding screens and drift often.
_USERNAME_INPUT = 'input[autocomplete="username"]'
_PASSWORD_INPUT = 'input[autocomplete="current-password"]'


async def login(timeout_seconds: int = 180) -> ActionResult:
    """Open a visible browser and wait for you to sign in to X interactively.

    Run the server with ``X_HEADLESS=false`` so the window is visible, call this
    tool, complete the login (including any 2FA / email step) in the browser, and
    the session is persisted to the on-disk profile for all later calls.

    Args:
        timeout_seconds: How long to wait for sign-in to complete before giving up.

    Returns:
        ActionResult with ``ok`` true once the authenticated UI is detected.
    """
    session = get_session()
    page = await session.new_page()
    try:
        await session.open_login(page)
        ok = await session.wait_until_authenticated(page, timeout_ms=timeout_seconds * 1_000)
        return ActionResult(
            ok=ok,
            action="login",
            message=(
                "Logged in; session persisted to the browser profile."
                if ok
                else "Timed out waiting for sign-in. Try a longer timeout or check the window."
            ),
        )
    finally:
        await page.close()


async def login_with_credentials() -> ActionResult:
    """Attempt an automated DOM login using X_USERNAME / X_PASSWORD (fragile).

    This types the configured credentials into the login form. It does NOT handle
    2FA, email confirmation, or the anti-bot challenges X frequently injects, so
    it only works for simple accounts. Prefer ``login`` or session cookies.

    Returns:
        ActionResult describing whether the session ended up authenticated.
    """
    settings = get_settings()
    if not settings.has_credentials:
        return ActionResult(
            ok=False,
            action="login_with_credentials",
            message="X_USERNAME and X_PASSWORD must be set to use automated login.",
        )

    session = get_session()
    page = await session.new_page()
    try:
        await session.open_login(page)

        await page.fill(_USERNAME_INPUT, settings.username or "")
        await page.keyboard.press("Enter")
        await asyncio.sleep(2.0)

        await page.fill(_PASSWORD_INPUT, settings.password or "")
        await page.keyboard.press("Enter")

        ok = await session.wait_until_authenticated(page, timeout_ms=30_000)
        return ActionResult(
            ok=ok,
            action="login_with_credentials",
            message=(
                "Logged in via credentials."
                if ok
                else "Login did not complete; X likely presented a challenge. "
                "Use the interactive `login` tool."
            ),
        )
    finally:
        await page.close()
