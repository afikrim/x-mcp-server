# Contributing to x-mcp-server

Thanks for your interest. This is a small, focused project: a stealth-browser MCP
server that reads and writes X (Twitter) content by driving an undetected Chrome
via Patchright, instead of paying for the X API. Contributions that keep it
simple and robust are very welcome.

## Project status

This project is built incrementally — features land when there's a real need for
them. As of the latest release, **verified working against live X**:

- **Login** — interactive sign-in (`--login`) with a persistent session.
- **Post a tweet** — `post_tweet`.

Everything else (`reply_to_tweet`, `like_tweet`, `follow_user`, and the read
tools `get_profile` / `get_user_tweets` / `get_tweet` / `search_tweets`) is
scaffolded and imports cleanly, but has **not** been validated end-to-end against
live X. Selector drift is expected. These will be hardened as the need arises —
see the [Roadmap](README.md#roadmap). If you need one of them, that's a great
place to contribute.

## Development setup

Requires [`uv`](https://docs.astral.sh/uv/) and Python >= 3.11.

```bash
uv sync                              # install deps into .venv
uv run patchright install chromium   # one-time browser download

uv run x-mcp-server --login          # sign in once (saves to ~/.x-mcp/profile)
uv run x-mcp-server --check-auth      # confirm the session is valid
```

To run the server locally over stdio:

```bash
uv run x-mcp-server
```

## Before you open a PR

```bash
uv run ruff format .   # format
uv run ruff check .    # lint (must pass)
uv run pytest          # tests (add some if you can!)
```

CI and reviewers expect `ruff check .` to be clean.

## Conventions

These keep the scraper resilient. Please follow them.

- **Selectors: `data-testid` only — never CSS class names.** X ships obfuscated,
  hashed class names that change every build; `data-testid` attributes are what
  X's own test suite uses and are far more stable. XPath that walks structure is
  also off-limits for the same reason. When X breaks the scraper, fix the JS in
  `extract.py` and the `wait_for` selectors in the tools — don't reach for
  classes or XPath.
- **Browser-driven, not API.** Write actions drive the real compose/action DOM
  rather than calling X's private GraphQL API. This avoids replicating X's
  request-signing (the `x-client-transaction-id` header) and keeps detection risk
  at browser level. See [docs/RESEARCH.md](docs/RESEARCH.md) for the
  reverse-engineered HTTP flow, kept only as a possible future path.
- **Config via `X_*` env vars** through `Settings` in `config.py`. No hardcoded
  paths or secrets. Update `.env.example` when you add a setting.
- **Handles** are accepted as `@name`, `name`, or a full URL — normalize through
  `extract.normalize_handle`.
- **Never commit real `auth_token` / `ct0` values** or a populated `.env`.

## Architecture (quick map)

- `server.py` — builds the FastMCP instance, registers tools, defines `check_auth`.
- `__main__.py` — the `x-mcp-server` CLI: `--login`, `--logout`, `--check-auth`,
  `--install`, and the default server mode.
- `browser.py` — the `BrowserSession` singleton: one persistent Patchright context,
  cookie injection, login-wall detection, navigation retries, Chromium
  auto-provisioning.
- `extract.py` — DOM extraction via `page.evaluate`. **The most fragile code in
  the repo**; expect to maintain this as X changes.
- `tools/` — one module per capability; wired in `tools/__init__.py:register`.
- `install.py` — `--install` writers for Claude Desktop, Claude Code, Codex,
  OpenCode.

## Testing UI changes

The browser flows can't be fully unit-tested, so verify against a real session.
`scripts/post_test.py` is a manual smoke test for the compose flow:

```bash
uv run python scripts/post_test.py "test post please delete"
```

It runs the browser **visibly** so you can watch the type + click. Use a
throwaway message and delete it afterward.

## Commit & PR guidelines

- Keep changes small and reversible.
- Write clear commit messages explaining the *why*, not just the *what*.
- Describe what you changed, how you tested it, and any risks.
- One logical change per PR where practical.

## Disclaimer

This tool is for research and personal use. Scraping may conflict with X's Terms
of Service; you are responsible for how you use it. Respect rate limits.
