"""Install this server into MCP client configs.

Each supported client stores MCP servers differently (JSON for Claude Desktop /
Claude Code / OpenCode, TOML for Codex) and in a different location. Every
installer here *merges* into the existing config so other servers are preserved,
and prefers a client's own CLI (which never corrupts its config) when available.

The installed entry launches the server straight from GitHub via ``uvx``, so the
client needs nothing beyond ``uv`` on PATH.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

from .exceptions import InstallError

logger = logging.getLogger(__name__)

# Identity of the server as written into client configs.
SERVER_NAME = "x-mcp-server"
GIT_URL = "git+https://github.com/afikrim/x-mcp-server.git"
COMMAND = "uvx"
ARGS = ["--from", GIT_URL, "x-mcp-server"]

CLIENTS = ("claude-desktop", "claude-code", "codex", "opencode")


def install(client: str) -> str:
    """Install the server into ``client`` and return a human-readable result."""
    installers: dict[str, Callable[[], str]] = {
        "claude-desktop": _install_claude_desktop,
        "claude-code": _install_claude_code,
        "codex": _install_codex,
        "opencode": _install_opencode,
    }
    try:
        return installers[client]()
    except KeyError:
        raise InstallError(
            f"Unknown client '{client}'. Choose one of: {', '.join(CLIENTS)}."
        ) from None


# --- shared helpers ---------------------------------------------------------


def _merge_json(path: Path, mutate: Callable[[dict], None]) -> None:
    """Load JSON from ``path`` (or {}), apply ``mutate``, and write it back."""
    data: dict = {}
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise InstallError(
                    f"Existing config at {path} is not valid JSON: {exc}"
                ) from exc
    mutate(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# --- Claude Desktop (JSON file, no CLI) -------------------------------------


def _claude_desktop_path() -> Path:
    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        return home / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", home))
        return base / "Claude/claude_desktop_config.json"
    return home / ".config/Claude/claude_desktop_config.json"


def _install_claude_desktop() -> str:
    path = _claude_desktop_path()

    def mutate(data: dict) -> None:
        data.setdefault("mcpServers", {})[SERVER_NAME] = {
            "command": COMMAND,
            "args": ARGS,
        }

    _merge_json(path, mutate)
    return f"Configured Claude Desktop at {path}\n  Restart Claude Desktop to load it."


# --- Claude Code (prefer `claude mcp` CLI, fall back to ~/.claude.json) ------


def _install_claude_code() -> str:
    entry = {"command": COMMAND, "args": ARGS}

    if shutil.which("claude"):
        result = subprocess.run(
            ["claude", "mcp", "add-json", SERVER_NAME, json.dumps(entry), "--scope", "user"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return "Added to Claude Code (user scope) via `claude mcp add-json`."
        # Most common non-zero: the server is already registered.
        detail = (result.stderr or result.stdout or "").strip()
        if "already exists" in detail.lower():
            return f"Claude Code already has '{SERVER_NAME}'; left unchanged."
        logger.warning("`claude mcp add-json` failed (%s); writing ~/.claude.json", detail)

    path = Path.home() / ".claude.json"

    def mutate(data: dict) -> None:
        data.setdefault("mcpServers", {})[SERVER_NAME] = entry

    _merge_json(path, mutate)
    return f"Configured Claude Code at {path} (user scope)."


# --- Codex (prefer `codex mcp add` CLI, fall back to ~/.codex/config.toml) ---


def _install_codex() -> str:
    if shutil.which("codex"):
        result = subprocess.run(
            ["codex", "mcp", "add", SERVER_NAME, "--", COMMAND, *ARGS],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return "Added to Codex via `codex mcp add`."
        detail = (result.stderr or result.stdout or "").strip()
        logger.warning("`codex mcp add` failed (%s); writing config.toml", detail)

    path = Path.home() / ".codex/config.toml"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    try:
        parsed = tomllib.loads(existing) if existing.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"Existing config at {path} is not valid TOML: {exc}") from exc

    if SERVER_NAME in parsed.get("mcp_servers", {}):
        return f"Codex already has [mcp_servers.{SERVER_NAME}] in {path}; left unchanged."

    # Hyphens are legal in TOML bare keys; JSON array == TOML array of strings.
    section = (
        f"\n[mcp_servers.{SERVER_NAME}]\n"
        f'command = "{COMMAND}"\n'
        f"args = {json.dumps(ARGS)}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(section)
    return f"Configured Codex at {path}"


# --- OpenCode (JSON file) ---------------------------------------------------


def _install_opencode() -> str:
    path = Path.home() / ".config/opencode/opencode.json"

    def mutate(data: dict) -> None:
        data.setdefault("$schema", "https://opencode.ai/config.json")
        data.setdefault("mcp", {})[SERVER_NAME] = {
            "type": "local",
            "command": [COMMAND, *ARGS],
            "enabled": True,
        }

    _merge_json(path, mutate)
    return f"Configured OpenCode at {path}"
