"""Stealth browser session management backed by Patchright.

A single persistent browser context is shared across all tool calls. The context
is launched lazily on first use and reused afterwards, which keeps cookies warm
and avoids paying browser-startup cost on every request.

Patchright is a drop-in, undetected fork of Playwright. To preserve its stealth
properties we deliberately avoid setting a custom user agent, extra headers, or a
fixed viewport, and we prefer the real Chrome channel. See
https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python for the rationale.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from patchright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .config import Settings, get_settings
from .exceptions import AuthenticationError, BrowserLaunchError, NavigationError

logger = logging.getLogger(__name__)

_LOGGED_IN_MARKER = '[data-testid="SideNav_AccountSwitcher_Button"]'
_LOGIN_URL_FRAGMENT = "/login"

# Chromium net errors that are worth retrying: the navigation failed for reasons
# unrelated to the page itself (network interface change, dropped connection, DNS
# hiccup, transient timeout). Auth redirects and 4xx pages are *not* in here.
_TRANSIENT_NAV_ERRORS = (
    "ERR_NETWORK_CHANGED",
    "ERR_NETWORK_IO_SUSPENDED",
    "ERR_INTERNET_DISCONNECTED",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_ABORTED",
    "ERR_CONNECTION_FAILED",
    "ERR_CONNECTION_TIMED_OUT",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_TIMED_OUT",
    "ERR_ABORTED",
)


def _is_transient_nav_error(exc: Exception) -> bool:
    message = str(exc)
    return any(code in message for code in _TRANSIENT_NAV_ERRORS)


# Substrings Patchright/Playwright uses when the browser binary isn't installed.
# Under `uvx`, the ephemeral env has no downloaded Chromium, so the very first
# launch hits one of these and we provision it on the fly.
_MISSING_BROWSER_MARKERS = (
    "Executable doesn't exist",
    "playwright install",
    "patchright install",
    "Chromium distribution",
    "is not found",
)


def _is_missing_browser_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _MISSING_BROWSER_MARKERS)


class BrowserSession:
    """Lazily-initialised, reusable Patchright browser context for x.com."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._lock = asyncio.Lock()

    async def _launch(self) -> BrowserContext:
        user_data_dir = Path(self._settings.user_data_dir).expanduser().resolve()
        user_data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Launching Patchright context (channel=%s, headless=%s, profile=%s)",
            self._settings.browser_channel,
            self._settings.headless,
            user_data_dir,
        )

        self._playwright = await async_playwright().start()
        context = await self._launch_context(user_data_dir)
        context.set_default_navigation_timeout(self._settings.nav_timeout_ms)
        await self._inject_session_cookies(context)
        return context

    async def _launch_context(self, user_data_dir: Path) -> BrowserContext:
        """Launch the persistent context, provisioning Chromium if it's missing.

        launch_persistent_context keeps cookies/localStorage on disk so a login
        survives restarts. Options are kept minimal for stealth.

        On a fresh ``uvx`` install no browser binary exists yet. The first launch
        then fails with a "browser not installed" error; we download bundled
        Chromium once and retry. If the configured channel (e.g. system ``chrome``)
        is what's missing, the retry falls back to bundled Chromium so the server
        still runs without a system Chrome install.
        """
        channel = self._settings.browser_channel or None
        try:
            return await self._open_context(user_data_dir, channel)
        except Exception as exc:  # noqa: BLE001 - inspected, then re-raised
            if not _is_missing_browser_error(exc):
                raise BrowserLaunchError(f"Failed to launch browser: {exc}") from exc

            logger.warning(
                "Browser '%s' is not installed (%s). Provisioning bundled Chromium...",
                channel or "chromium",
                exc,
            )
            await self._install_chromium()
            try:
                # Retry with bundled Chromium (channel=None), which the install
                # just provided, regardless of the originally configured channel.
                return await self._open_context(user_data_dir, None)
            except Exception as retry_exc:  # noqa: BLE001
                raise BrowserLaunchError(
                    f"Browser still failed to launch after installing Chromium: {retry_exc}"
                ) from retry_exc

    async def _open_context(self, user_data_dir: Path, channel: str | None) -> BrowserContext:
        return await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            channel=channel,
            headless=self._settings.headless,
            no_viewport=True,
        )

    async def _install_chromium(self) -> None:
        """Download Patchright's bundled Chromium via `python -m patchright install`."""
        logger.info("Downloading Chromium (one-time, ~150MB)...")
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "patchright",
            "install",
            "chromium",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        if proc.returncode != 0:
            raise BrowserLaunchError(
                "Failed to install Chromium "
                f"(exit {proc.returncode}): {out.decode(errors='replace').strip()}"
            )
        logger.info("Chromium installed.")

    async def _inject_session_cookies(self, context: BrowserContext) -> None:
        """Seed the context with auth cookies from settings, when provided."""
        if not self._settings.auth_token:
            return

        cookies = [
            {
                "name": "auth_token",
                "value": self._settings.auth_token,
                "domain": ".x.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }
        ]
        if self._settings.csrf_token:
            cookies.append(
                {
                    "name": "ct0",
                    "value": self._settings.csrf_token,
                    "domain": ".x.com",
                    "path": "/",
                    "secure": True,
                }
            )
        await context.add_cookies(cookies)
        logger.info("Injected %d session cookie(s) into the browser context.", len(cookies))

    async def context(self) -> BrowserContext:
        """Return the shared context, launching it on first use."""
        if self._context is None:
            async with self._lock:
                if self._context is None:
                    self._context = await self._launch()
        return self._context

    async def new_page(self) -> Page:
        ctx = await self.context()
        return await ctx.new_page()

    async def goto(self, page: Page, url: str, *, wait_for: str | None = None) -> None:
        """Navigate ``page`` to ``url`` and optionally wait for a selector.

        Raises:
            NavigationError: if the page never loads or the selector never appears.
            AuthenticationError: if X redirects to the login wall.
        """
        attempts = max(1, self._settings.nav_retries)
        for attempt in range(1, attempts + 1):
            try:
                await page.goto(url, wait_until="domcontentloaded")
            except Exception as exc:  # noqa: BLE001 - re-wrapped with context
                if attempt < attempts and _is_transient_nav_error(exc):
                    backoff = 0.5 * 2 ** (attempt - 1)
                    logger.warning(
                        "Transient nav error loading %s (attempt %d/%d): %s; retrying in %.1fs",
                        url,
                        attempt,
                        attempts,
                        exc,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise NavigationError(f"Failed to load {url}: {exc}") from exc
            else:
                break

        if _LOGIN_URL_FRAGMENT in page.url:
            raise AuthenticationError(
                "X redirected to the login page. Provide a valid X_AUTH_TOKEN "
                "or run the interactive login."
            )

        if wait_for:
            try:
                await page.wait_for_selector(wait_for, timeout=self._settings.nav_timeout_ms)
            except Exception as exc:  # noqa: BLE001
                raise NavigationError(
                    f"Timed out waiting for '{wait_for}' on {url}: {exc}"
                ) from exc

    async def open_login(self, page: Page) -> None:
        """Navigate ``page`` to the X login screen.

        Used by the interactive ``login`` tool. The caller is expected to launch
        the browser non-headless (``X_HEADLESS=false``) so a human can complete
        the username/password/2FA challenge in the visible window.
        """
        try:
            await page.goto("https://x.com/login", wait_until="domcontentloaded")
        except Exception as exc:  # noqa: BLE001
            raise NavigationError(f"Failed to open the login page: {exc}") from exc

    async def wait_until_authenticated(self, page: Page, timeout_ms: int | None = None) -> bool:
        """Block until the logged-in marker appears on ``page`` or the timeout elapses.

        Returns True once X shows the authenticated chrome (the account switcher),
        which is when the persistent context has captured the session cookies.
        """
        timeout = timeout_ms or self._settings.login_timeout_ms
        try:
            await page.wait_for_selector(_LOGGED_IN_MARKER, timeout=timeout)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def is_authenticated(self) -> bool:
        """Best-effort check that the current session is logged in to X."""
        page = await self.new_page()
        try:
            await page.goto("https://x.com/home", wait_until="domcontentloaded")
            if _LOGIN_URL_FRAGMENT in page.url:
                return False
            try:
                await page.wait_for_selector(_LOGGED_IN_MARKER, timeout=8_000)
                return True
            except Exception:  # noqa: BLE001
                return False
        finally:
            await page.close()

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


_session: BrowserSession | None = None


def get_session() -> BrowserSession:
    """Return the process-wide browser session singleton."""
    global _session
    if _session is None:
        _session = BrowserSession()
    return _session
