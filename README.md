# x-mcp-server

An [MCP](https://modelcontextprotocol.io) server that scrapes public content from
**X** (formerly Twitter) using a stealth [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python)
browser, exposed over [FastMCP](https://github.com/jlowin/fastmcp). Designed to run
with `uvx`, so any MCP client can launch it with zero local setup.

> Inspired by [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server).

## Why a browser instead of the API

X's official API is expensive and heavily gated. This server drives a real,
undetected Chrome session via Patchright and reads the rendered page, so it works
with a normal logged-in account. Selectors target X's stable `data-testid`
attributes and will need occasional maintenance as the UI changes.

## Tools

| Tool | Description |
| --- | --- |
| `get_profile(username)` | Display name, bio, location, website, join date, follower/following counts. |
| `get_user_tweets(username, limit=20)` | A user's most recent posts from their timeline. |
| `get_tweet(url_or_id)` | A single post by URL or numeric status id. |
| `search_tweets(query, limit=20, latest=True)` | Search across X; supports operators like `from:`, `min_faves:`, `#tag`. |
| `check_auth()` | Diagnose whether the session is logged in. |

Handles may be passed as `@name`, `name`, or a full `https://x.com/name` URL.

## Roadmap

The current scope is intentionally minimal: **sign in and start posting**.
Everything below is a TODO, modelled on the capabilities of
[stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server)
(the project that inspired this one) and adapted to X.

**Near-term (the current focus)**

- [ ] Interactive sign-in flow — a `--login` / `--logout` CLI flag that opens a
  browser for manual auth, persisting the session instead of pasting cookies.
- [ ] `post_tweet(text)` — publish a post from the logged-in account.

**Write actions (X-native, inspired by `connect_with_person` / `send_message`)**

- [ ] `reply_to_tweet`, `quote_tweet`
- [ ] `like_tweet`, `repost`
- [ ] `delete_tweet`
- [ ] `follow` / `unfollow`
- [ ] `send_dm`, `get_inbox`, `get_conversation`, `search_conversations`
  (mirrors LinkedIn's messaging tools)

**Read actions**

- [ ] `get_my_profile` — the authenticated user's own profile (`get_my_profile`).
- [ ] `get_home_timeline` — the logged-in home feed (`get_feed`).
- [ ] `search_users` — people search (`search_people`).
- [ ] `get_who_to_follow` — recommended accounts (`get_sidebar_profiles`).

**Session & tooling**

- [ ] `close_session` tool to terminate the browser and clean up.
- [ ] Streamable HTTP transport in addition to stdio.
- [ ] Claude Desktop one-click `.mcpb` bundle.
- [ ] Secure credential storage via the system keyring.

## Authentication

Most X content requires a logged-in session. Provide your session cookies via
environment variables (copy `.env.example` to `.env`):

```bash
X_AUTH_TOKEN=...   # the `auth_token` cookie from x.com
X_CSRF_TOKEN=...   # the `ct0` cookie (optional but recommended)
```

To grab them: log in to x.com, open DevTools → Application → Cookies →
`https://x.com`, and copy `auth_token` and `ct0`.

Alternatively, run once with `X_HEADLESS=false` and log in interactively; the
session is persisted in `X_USER_DATA_DIR` for subsequent headless runs.

## Run

### With uvx (recommended)

```bash
uvx --from . x-mcp-server          # from a checkout
# once published to PyPI:
uvx x-mcp-server
```

First run needs the browser binaries:

```bash
uvx --from . --with patchright patchright install chromium
```

### MCP client config

```json
{
  "mcpServers": {
    "x": {
      "command": "uvx",
      "args": ["x-mcp-server"],
      "env": {
        "X_AUTH_TOKEN": "your_auth_token",
        "X_CSRF_TOKEN": "your_ct0"
      }
    }
  }
}
```

### Local development

```bash
uv sync
uv run patchright install chromium
uv run x-mcp-server
```

### Docker

```bash
docker build -t x-mcp-server .
docker run --rm -i -e X_AUTH_TOKEN=... -e X_CSRF_TOKEN=... x-mcp-server
```

## Configuration

All settings are environment variables (prefix `X_`). See [`.env.example`](.env.example)
for the full list: `X_HEADLESS`, `X_USER_DATA_DIR`, `X_BROWSER_CHANNEL`,
`X_NAV_TIMEOUT_MS`, `X_LOG_LEVEL`.

## Disclaimer

For research and personal use. Scraping may conflict with X's Terms of Service;
you are responsible for how you use this tool. Respect rate limits and applicable
law.

## Credits

This project is directly inspired by
[stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server)
by [Daniel Sticker](https://github.com/stickerdaniel) — a stealth-browser MCP
server for LinkedIn. The architecture (Patchright + FastMCP, cookie/session auth,
`uvx` distribution) and the [Roadmap](#roadmap) above follow its design. Go give
it a star.

## License

MIT — see [LICENSE](LICENSE).
