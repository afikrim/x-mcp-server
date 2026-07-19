"""Tests for browser and Xquik search backends."""

from __future__ import annotations

import io
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from x_mcp_server.tools import search


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_xquik_search_uses_current_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    request_details: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: int) -> _Response:
        request_details["request"] = request
        request_details["timeout"] = timeout
        return _Response(
            b'{"tweets":[{"id":"42","text":"Hello","createdAt":"2026-07-18T00:00:00Z",'
            b'"replyCount":1,"retweetCount":2,"likeCount":3,"viewCount":4,'
            b'"author":{"userName":"alice","name":"Alice"}}]}'
        )

    monkeypatch.setattr(search, "urlopen", fake_urlopen)

    tweets = search._xquik_search_sync("agents/tools", 7, False, "xq_test")

    assert len(tweets) == 1
    assert tweets[0].model_dump() == {
        "id": "42",
        "url": "https://x.com/alice/status/42",
        "author_handle": "@alice",
        "author_name": "Alice",
        "text": "Hello",
        "created_at": "2026-07-18T00:00:00Z",
        "reply_count": 1,
        "repost_count": 2,
        "like_count": 3,
        "view_count": 4,
    }
    request = request_details["request"]
    assert isinstance(request, Request)
    assert request.get_header("User-agent") == "mcp-server-x"
    assert request.get_header("X-api-key") == "xq_test"
    query = parse_qs(urlparse(request.full_url).query)
    assert query == {"limit": ["7"], "q": ["agents/tools"], "queryType": ["Top"]}
    assert request_details["timeout"] == 30


def test_tweet_mapping_skips_blank_and_boolean_values() -> None:
    tweet = search._tweet_from_xquik(
        {
            "id": " 43 ",
            "text": "  useful result  ",
            "replyCount": True,
            "author": {"userName": "  @bob  "},
        }
    )

    assert tweet.id == "43"
    assert tweet.author_handle == "@bob"
    assert tweet.text == "useful result"
    assert tweet.reply_count is None


@pytest.mark.asyncio
async def test_blank_xquik_key_keeps_browser_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XQUIK_API_KEY", "   ")

    result = await search._search_xquik("query", 20, True)

    assert result is None


def test_http_error_does_not_expose_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: int) -> _Response:
        del request, timeout
        raise HTTPError(
            "https://xquik.com/api/v1/x/tweets/search",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b"sensitive upstream detail"),
        )

    monkeypatch.setattr(search, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match=r"^Xquik search failed with HTTP 401\.$") as exc_info:
        search._xquik_search_sync("query", 20, True, "xq_test")

    assert "sensitive" not in str(exc_info.value)


def test_invalid_json_has_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search, "urlopen", lambda request, timeout: _Response(b"not json"))

    with pytest.raises(
        RuntimeError,
        match=r"^Xquik search returned an invalid JSON response\.$",
    ):
        search._xquik_search_sync("query", 20, True, "xq_test")


@pytest.mark.parametrize(
    "response",
    [b"[]", b'{"tweets":"invalid"}', b'{"tweets":[{"id":"1"},"invalid"]}'],
)
def test_invalid_response_shape_has_clear_error(
    monkeypatch: pytest.MonkeyPatch, response: bytes
) -> None:
    monkeypatch.setattr(search, "urlopen", lambda request, timeout: _Response(response))

    with pytest.raises(
        RuntimeError,
        match=r"^Xquik search returned an invalid response shape\.$",
    ):
        search._xquik_search_sync("query", 20, True, "xq_test")


@pytest.mark.asyncio
async def test_browser_search_encodes_slashes(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePage:
        async def close(self) -> None:
            return None

    class FakeSession:
        def __init__(self) -> None:
            self.url = ""

        async def new_page(self) -> FakePage:
            return FakePage()

        async def goto(self, page: FakePage, url: str, wait_for: str) -> None:
            del page, wait_for
            self.url = url

    async def fake_collect(page: FakePage, limit: int) -> list[object]:
        del page, limit
        return []

    session = FakeSession()
    monkeypatch.delenv("XQUIK_API_KEY", raising=False)
    monkeypatch.setattr(search, "get_session", lambda: session)
    monkeypatch.setattr(search, "collect_tweets", fake_collect)

    result = await search.search_tweets("agents/tools", limit=3)

    assert result == []
    assert session.url == "https://x.com/search?q=agents%2Ftools&src=typed_query&f=live"
