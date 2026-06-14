# x-mcp-server

An [MCP](https://modelcontextprotocol.io) server that scrapes public content from
**X** (formerly Twitter) using a stealth [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python)
browser, exposed over [FastMCP](https://github.com/jlowin/fastmcp). Designed to run
with `uvx`, so any MCP client can launch it with zero local setup.

> Inspired by [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server).

> **Disclaimer:** This is an independent, community project. It is not affiliated
> with, authorized by, endorsed by, or sponsored by X Corp. "X" and "Twitter" are
> trademarks of X Corp, used here only descriptively to identify the third-party
> service this software interoperates with.

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
| `login(timeout_seconds=180)` | Open a visible browser and sign in interactively; persists the session. |
| `login_with_credentials()` | Best-effort automated DOM login from `X_USERNAME`/`X_PASSWORD` (no 2FA). |
| `post_tweet(text)` | Publish a post from the logged-in account. |
| `reply_to_tweet(url_or_id, text)` | Reply to an existing post. |
| `like_tweet(url_or_id)` | Like a post. |
| `follow_user(username)` | Follow a user from their profile. |

Handles may be passed as `@name`, `name`, or a full `https://x.com/name` URL.
Write tools require an authenticated session (run `login` or set `X_AUTH_TOKEN`).
See [docs/RESEARCH.md](docs/RESEARCH.md) for the reverse-engineered login/post
HTTP flow behind a future browserless implementation.

## Roadmap

The current scope is intentionally minimal: **sign in and start posting**.
Everything below is a TODO, modelled on the capabilities of
[stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server)
(the project that inspired this one) and adapted to X.

**Near-term (the current focus)**

- [x] Interactive sign-in — the `login` tool opens a browser for manual auth and
  persists the session (run with `X_HEADLESS=false`). Cookie auth still works.
- [x] `post_tweet(text)` — publish a post from the logged-in account.

> Scaffolded but **not yet validated against live X** — selectors and the compose
> DOM drift. Verify with a real session before trusting output.

**Write actions (X-native, inspired by `connect_with_person` / `send_message`)**

- [x] `reply_to_tweet`
- [ ] `quote_tweet`
- [x] `like_tweet`
- [ ] `repost`
- [ ] `delete_tweet`
- [x] `follow_user`
- [ ] `unfollow`
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

Most X content requires a logged-in session. Two options:

### Option 1: Interactive login (recommended)

```bash
uv run x-mcp-server --login
```

This opens a browser where you sign in manually (handles 2FA and challenges).
The session is saved to `X_USER_DATA_DIR` (default: `~/.x-mcp/profile`) and reused
on all future runs — no cookie management needed.

### Option 2: Manual session cookies

Set environment variables in `.env` (copy from `.env.example`):

```bash
X_AUTH_TOKEN=...   # the `auth_token` cookie from x.com
X_CSRF_TOKEN=...   # the `ct0` cookie (optional but recommended)
```

To grab them: log in to x.com, open DevTools → Application → Cookies →
`https://x.com`, and copy `auth_token` and `ct0`.

### Verify authentication

```bash
uv run x-mcp-server --check-auth
```

### Clear the saved session

```bash
uv run x-mcp-server --logout
```

## Run

### With uvx, straight from GitHub (recommended)

No PyPI install needed — `uvx` runs it directly from the repo:

```bash
# one-time interactive login (opens a browser, saves the session)
uvx --from git+https://github.com/afikrim/x-mcp-server.git x-mcp-server --login

# then run the server
uvx --from git+https://github.com/afikrim/x-mcp-server.git x-mcp-server
```

Pin a tag or commit for reproducibility, e.g.
`git+https://github.com/afikrim/x-mcp-server.git@v0.1.0`.

The Chromium browser is **auto-provisioned on first launch** if it isn't already
present, so there's no separate `patchright install` step. (It downloads ~150MB
once into the Patchright browser cache.)

### Install into an MCP client (automatic)

`--install` writes the config for you, merging into the client's existing servers
(it never clobbers other entries) and using each client's own CLI when available:

```bash
uvx --from git+https://github.com/afikrim/x-mcp-server.git x-mcp-server --install claude-desktop
uvx --from git+https://github.com/afikrim/x-mcp-server.git x-mcp-server --install claude-code
uvx --from git+https://github.com/afikrim/x-mcp-server.git x-mcp-server --install codex
uvx --from git+https://github.com/afikrim/x-mcp-server.git x-mcp-server --install opencode
```

| Client | Config written |
| --- | --- |
| `claude-desktop` | `claude_desktop_config.json` (platform-specific path) |
| `claude-code` | `claude mcp add-json` (user scope), else `~/.claude.json` |
| `codex` | `codex mcp add`, else `~/.codex/config.toml` |
| `opencode` | `~/.config/opencode/opencode.json` |

Restart the client afterward. Run `--login` once (see above) so the session
exists before the client first calls a tool.

### MCP client config (manual)

If you'd rather configure by hand:

```json
{
  "mcpServers": {
    "x-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/afikrim/x-mcp-server.git",
        "x-mcp-server"
      ]
    }
  }
}
```

No `env` block is needed once you've run `--login` — the session is read from
`~/.x-mcp/profile`. (You can still pass `X_AUTH_TOKEN` / `X_CSRF_TOKEN` instead.)

### Local development

```bash
uv sync
uv run patchright install chromium

# Option 1: Interactive login (saves session for future runs)
uv run x-mcp-server --login

# Option 2: Run the server (with X_AUTH_TOKEN/X_CSRF_TOKEN from .env)
uv run x-mcp-server

# Check auth status
uv run x-mcp-server --check-auth

# Clear the saved session
uv run x-mcp-server --logout
```

**CLI flags:**

- `--login` — Open browser for interactive sign-in, save session.
- `--logout` — Clear the saved browser profile.
- `--check-auth` — Check if the session is authenticated and exit.
- `--install {claude-desktop,claude-code,codex,opencode}` — Register the server in a client's config and exit.
- `--no-headless` — Show the browser window (useful for debugging login).
- `--log-level {DEBUG,INFO,WARNING,ERROR}` — Set verbosity (default: INFO).

### Docker

```bash
docker build -t x-mcp-server .
docker run --rm -i -e X_AUTH_TOKEN=... -e X_CSRF_TOKEN=... x-mcp-server
```

## Configuration

All settings are environment variables (prefix `X_`). See [`.env.example`](.env.example)
for the full list: `X_HEADLESS`, `X_USER_DATA_DIR`, `X_BROWSER_CHANNEL`,
`X_NAV_TIMEOUT_MS`, `X_LOG_LEVEL`.

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
conventions (notably: `data-testid` selectors only, browser-driven not API), and
the current feature status.

## Disclaimer & responsible use

**This tool is for personal and research use only, and comes with no warranty of
any kind.** Use it in accordance with [X's Terms of Service](https://x.com/tos).

### Is this safe? Will I get banned?

This server controls a real, logged-in browser session — it does **not** exploit
undocumented APIs or bypass authentication. That said, X's Terms of Service
prohibit scraping and automated access without prior consent, and accounts using
automated tools **can be rate-limited, restricted, or banned**. There is no
guarantee of account safety. Use at your own risk, and prefer an account you can
afford to lose.

Because the session is authenticated, you have agreed to X's terms — so the risk
here is contractual (breach of the ToS) and operational (account action), not
just abstract. See the [LinkedIn precedent (hiQ v. LinkedIn)](https://en.wikipedia.org/wiki/HiQ_Labs_v._LinkedIn)
for how courts have treated authenticated scraping versus public-data scraping.

### Keep volume sane

You are responsible for the volume of automation you run. Use it sparingly,
keep pacing human-like, respect rate limits, and prompt your agents responsibly.
Do not redistribute, resell, or build public datasets from the output.

### For anything commercial or at scale

Use the [official X API](https://developer.x.com/), or obtain written consent
from X. The browser route is not defensible at scale — switch to a licensed path
before you grow beyond personal use.

## Credits

This project is directly inspired by
[stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server)
by [Daniel Sticker](https://github.com/stickerdaniel) — a stealth-browser MCP
server for LinkedIn. The architecture (Patchright + FastMCP, cookie/session auth,
`uvx` distribution) and the [Roadmap](#roadmap) above follow its design. Go give
it a star.

## License

MIT — see [LICENSE](LICENSE).
