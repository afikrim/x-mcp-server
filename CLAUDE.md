# x-mcp-server

A stealth-browser MCP server that reads and writes content on **X** (formerly
Twitter) and exposes it over **FastMCP**. It drives an undetected Chrome via
**Patchright** and operates the rendered DOM, so it works with a normal logged-in
account instead of the paid X API. Inspired by `stickerdaniel/linkedin-mcp-server`.

Designed to run via `uvx` straight from GitHub, so any MCP client can launch it
with no local setup.

## Stack

- Python >= 3.11, packaged with `hatchling`, dependency/run via `uv`
- `fastmcp` for the MCP layer (stdio transport)
- `patchright` (undetected Playwright fork) for the browser
- `pydantic` / `pydantic-settings` for models and config

## Commands

```bash
uv sync                              # install deps into .venv
uv run patchright install chromium   # one-time browser download (auto on first run too)

uv run x-mcp-server --login          # interactive sign-in; saves to ~/.x-mcp/profile
uv run x-mcp-server --check-auth     # verify the session is valid
uv run x-mcp-server                  # run the server over stdio
uvx --from . x-mcp-server            # run from a checkout without installing

uv run ruff check .                  # lint (must pass)
uv run ruff format .                 # format
uv run pytest                        # tests (none yet)
```

## Architecture

- `x_mcp_server/server.py` — builds the `FastMCP` instance, registers tools, defines `check_auth`. Module-level `mcp` is the entry object.
- `x_mcp_server/__main__.py` — the `x-mcp-server` console script (CLI): `--login`, `--logout`, `--check-auth`, `--install`, `--no-headless`; with no flag it runs `mcp.run()` over stdio. CLI auth commands close the browser cleanly inside the event loop.
- `x_mcp_server/browser.py` — `BrowserSession` singleton: one persistent Patchright context, launched lazily and reused. Injects `auth_token`/`ct0` cookies, detects the `/login` wall, retries transient network errors with backoff, and auto-provisions Chromium when missing.
- `x_mcp_server/extract.py` — DOM extraction. Runs JS in the page via `page.evaluate`, targets stable `data-testid` selectors. **This is the most fragile code in the repo.**
- `x_mcp_server/config.py` — `Settings` from `X_*` env vars (and `.env`). `user_data_dir` defaults to `~/.x-mcp/profile`; a validator expands `~` and `$VAR`.
- `x_mcp_server/install.py` — `--install` writers for Claude Desktop, Claude Code, Codex, OpenCode (merge into existing config; prefer the client's CLI when present).
- `x_mcp_server/tools/` — one module per capability (`profile`, `timeline`, `search`, `auth`, `post`), wired in `tools/__init__.py:register`. `_common.collect_tweets` handles scroll pagination.

Tools: `get_profile`, `get_user_tweets`, `get_tweet`, `search_tweets`, `check_auth`, `login`, `login_with_credentials`, `post_tweet`, `reply_to_tweet`, `like_tweet`, `follow_user`.

## Conventions

- Tools are plain async functions; `register(mcp)` attaches them. Keep tool impls decoupled from the `mcp` instance.
- **Selectors are obfuscation-resistant `data-testid` attributes only — never CSS class names or XPath.** When X breaks, fix the JS in `extract.py` and the `wait_for` selectors in the tools.
- **Browser-driven, not API.** Write actions operate the compose/action DOM rather than X's private GraphQL API (avoids the `x-client-transaction-id` signing and keeps detection at browser level). `docs/RESEARCH.md` documents the HTTP flow only as a possible future path.
- All config is `X_*` env vars via `Settings`; no hardcoded paths or secrets. Update `.env.example` when adding a setting.
- Handles accepted as `@name`, `name`, or full URL — normalize through `extract.normalize_handle`.
- Auth is session-based (persistent browser profile) or cookie-based; never commit real `auth_token`/`ct0` values.

## Project-specific caveats

- **Verified against live X:** `--login` (interactive sign-in) and `post_tweet`. Everything else (`reply_to_tweet`, `like_tweet`, `follow_user`, and the read tools) is scaffolded and imports cleanly but is **not** validated end-to-end — selector drift is expected; harden as needed.
- The compose surface is Draft.js: `page.fill` does not register input (button stays disabled). Type real keystrokes (`press_sequentially`) into the `primaryColumn`-scoped composer; `/compose/post` opens a modal that duplicates `tweetTextarea_0`.
- X requires a logged-in session for most content. Empty results usually mean auth, not a bug — check `check_auth` first.
- Respect rate limits. This is for research/personal use and may conflict with X's ToS.
