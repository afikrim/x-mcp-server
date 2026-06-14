"""Structured result models returned by the MCP tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Tweet(BaseModel):
    """A single post on X."""

    id: str | None = Field(default=None, description="Numeric status id, if resolvable.")
    url: str | None = Field(default=None, description="Canonical permalink to the post.")
    author_handle: str | None = Field(default=None, description="@handle of the author.")
    author_name: str | None = Field(default=None, description="Display name of the author.")
    text: str = Field(default="", description="The post's text content.")
    created_at: str | None = Field(default=None, description="ISO 8601 timestamp from the post.")
    reply_count: int | None = None
    repost_count: int | None = None
    like_count: int | None = None
    view_count: int | None = None


class Profile(BaseModel):
    """A user profile on X."""

    handle: str = Field(description="@handle without the leading @.")
    name: str | None = Field(default=None, description="Display name.")
    bio: str | None = Field(default=None, description="Profile bio / description.")
    location: str | None = None
    website: str | None = None
    joined: str | None = Field(default=None, description="Human-readable join date.")
    following_count: str | None = None
    followers_count: str | None = None
    verified: bool = False


class ActionResult(BaseModel):
    """Outcome of a write action (post, reply, like, follow, login)."""

    ok: bool = Field(description="Whether the action completed successfully.")
    action: str = Field(description="The action that was attempted, e.g. 'post_tweet'.")
    message: str = Field(default="", description="Human-readable detail about the outcome.")
    url: str | None = Field(
        default=None, description="Permalink to the created/affected post, if any."
    )
    id: str | None = Field(
        default=None, description="Numeric status id of the created/affected post, if resolvable."
    )
