"""DOM extraction helpers.

X renders entirely client-side and its markup is obfuscated, so we lean on the
stable ``data-testid`` attributes rather than CSS class names. Extraction runs
inside the page via ``page.evaluate`` so we get a structured snapshot in one round
trip. Selectors here are the most fragile part of the project and are expected to
need occasional maintenance as X ships UI changes.
"""

from __future__ import annotations

import re

from patchright.async_api import Page

from .models import Profile, Tweet

# JS that scrapes every rendered tweet <article> on the current page.
_TWEETS_JS = r"""
() => {
  const parseCount = (label, kind) => {
    if (!label) return null;
    const re = new RegExp("([0-9.,KMB]+)\\s+" + kind, "i");
    const m = label.match(re);
    if (!m) return null;
    let n = m[1].replace(/,/g, "");
    const mult = { K: 1e3, M: 1e6, B: 1e9 };
    const suffix = n.slice(-1).toUpperCase();
    if (mult[suffix]) return Math.round(parseFloat(n) * mult[suffix]);
    return parseInt(n, 10) || null;
  };

  const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
  return articles.map((a) => {
    const textEl = a.querySelector('[data-testid="tweetText"]');
    const timeEl = a.querySelector('time');
    const permalink = timeEl ? timeEl.closest('a') : null;
    const url = permalink ? permalink.href : null;
    const idMatch = url ? url.match(/status\/(\d+)/) : null;

    // The action bar group carries an aria-label like
    // "3 replies, 12 reposts, 88 likes, 5 bookmarks, 1234 views".
    const group = a.querySelector('[role="group"]');
    const label = group ? group.getAttribute('aria-label') : null;

    const userNameBlock = a.querySelector('[data-testid="User-Name"]');
    let authorName = null, authorHandle = null;
    if (userNameBlock) {
      const spans = Array.from(userNameBlock.querySelectorAll('span'))
        .map((s) => s.textContent).filter(Boolean);
      authorName = spans[0] || null;
      const handle = spans.find((s) => s.startsWith('@'));
      authorHandle = handle ? handle.replace(/^@/, '') : null;
    }

    return {
      id: idMatch ? idMatch[1] : null,
      url,
      author_handle: authorHandle,
      author_name: authorName,
      text: textEl ? textEl.textContent : "",
      created_at: timeEl ? timeEl.getAttribute('datetime') : null,
      reply_count: parseCount(label, 'repl(?:y|ies)'),
      repost_count: parseCount(label, 'reposts?'),
      like_count: parseCount(label, 'likes?'),
      view_count: parseCount(label, 'views?'),
    };
  });
}
"""

_PROFILE_JS = r"""
() => {
  const q = (sel) => document.querySelector(sel);
  const txt = (sel) => { const e = q(sel); return e ? e.textContent.trim() : null; };
  const nameEl = q('[data-testid="UserName"]');
  let name = null, handle = null;
  if (nameEl) {
    const spans = Array.from(nameEl.querySelectorAll('span'))
      .map((s) => s.textContent).filter(Boolean);
    name = spans[0] || null;
    const h = spans.find((s) => s.startsWith('@'));
    handle = h ? h.replace(/^@/, '') : null;
  }
  const link = q('[data-testid="UserUrl"]');
  return {
    name,
    handle,
    bio: txt('[data-testid="UserDescription"]'),
    location: txt('[data-testid="UserLocation"]'),
    website: link ? (link.getAttribute('href') || link.textContent.trim()) : null,
    joined: txt('[data-testid="UserJoinDate"]'),
    verified: !!q('[data-testid="UserName"] svg[aria-label*="Verified"]'),
  };
}
"""

_FOLLOW_JS = r"""
() => {
  const out = { following_count: null, followers_count: null };
  const links = Array.from(document.querySelectorAll('a[href$="/following"], a[href$="/verified_followers"], a[href$="/followers"]'));
  for (const l of links) {
    const span = l.querySelector('span');
    const val = span ? span.textContent.trim() : null;
    if (l.href.endsWith('/following')) out.following_count = val;
    else out.followers_count = out.followers_count || val;
  }
  return out;
}
"""


async def extract_tweets(page: Page, limit: int) -> list[Tweet]:
    raw = await page.evaluate(_TWEETS_JS)
    tweets = [Tweet(**item) for item in raw if item.get("text") or item.get("url")]
    return tweets[:limit]


async def extract_profile(page: Page, handle: str) -> Profile:
    raw = await page.evaluate(_PROFILE_JS)
    follow = await page.evaluate(_FOLLOW_JS)
    raw.setdefault("handle", handle)
    raw["handle"] = raw.get("handle") or handle
    return Profile(**{**raw, **follow})


def normalize_handle(value: str) -> str:
    """Strip URLs, leading @, and whitespace from a user-supplied handle."""
    value = value.strip()
    m = re.search(r"(?:x\.com|twitter\.com)/([A-Za-z0-9_]+)", value)
    if m:
        return m.group(1)
    return value.lstrip("@")
