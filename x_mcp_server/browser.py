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
from pathlib import Path

from patchright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .config import Settings, get_settings
from .exceptions import AuthenticationError, NavigationError

logger = logging.getLogger(__name__)

_LOGGED_IN_MARKER = '[data-testid="SideNav_AccountSwitcher_Button"]'
_LOGIN_URL_FRAGMENT = "/login"


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
        # launch_persistent_context keeps cookies/localStorage on disk so a login
        # survives restarts. Keep the option set minimal for stealth.
        context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            channel=self._settings.browser_channel or None,
            headless=self._settings.headless,
            no_viewport=True,
        )
        context.set_default_navigation_timeout(self._settings.nav_timeout_ms)
        await self._inject_session_cookies(context)
        return context

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
        try:
            await page.goto(url, wait_until="domcontentloaded")
        except Exception as exc:  # noqa: BLE001 - re-wrapped with context
            raise NavigationError(f"Failed to load {url}: {exc}") from exc

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
