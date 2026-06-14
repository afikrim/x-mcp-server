# Reverse-engineering X (Twitter) login and posting

Research notes backing the write/login scaffold. The current implementation
drives the **web UI** through Patchright (`tools/auth.py`, `tools/post.py`). This
doc records the **browserless HTTP path** that the private X clients actually use,
so a future version can drop the browser for write actions. None of this uses the
paid X API; it replays the same calls `x.com` makes from your browser.

> Status: research + scaffold only. The HTTP flow below is **not implemented**
> yet. Selectors and query ids drift; verify against live traffic before relying
> on any of it. This is for research / personal use and may conflict with X's ToS.

## 1. The three credentials that gate everything

| Credential | Where it comes from | Used as |
| --- | --- | --- |
| **Bearer token** | A hardcoded public constant shipped in X's web JS. The well-known web value is `AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA`. | `authorization: Bearer <token>` on every request |
| **`ct0`** | A cookie set during login. `ct0` and the `x-csrf-token` header are **the same value**. | `x-csrf-token: <ct0>` header + `ct0` cookie (double-submit CSRF) |
| **`auth_token`** | The session cookie set on successful login. | `auth_token` cookie; this *is* the logged-in session |

If you already have `auth_token` + `ct0` (copy them from a logged-in browser's
DevTools → Application → Cookies), you can skip the login flow entirely and go
straight to authenticated GraphQL calls. That is exactly what `X_AUTH_TOKEN` /
`X_CSRF_TOKEN` in this repo do.

## 2. Login flow (`/1.1/onboarding/task.json`)

Login is a **state machine**. You POST subtasks one at a time; each response
returns a fresh `flow_token` you echo into the next request, plus the list of the
next subtask(s) X expects. Order observed in the wild:

1. **Activate a guest token** — `POST https://api.twitter.com/1.1/guest/activate.json`
   with the bearer header. Returns `guest_token`, sent thereafter as
   `x-guest-token`.
2. **Start the flow** — `POST .../onboarding/task.json?flow_name=login` →
   first `flow_token` + `LoginJsInstrumentationSubtask`.
3. **`LoginJsInstrumentationSubtask`** — submit a (usually empty `{}`) JS
   instrumentation response.
4. **`LoginEnterUserIdentifierSSO`** — submit the username/email in a
   `settings_list` enter-text input.
5. **`LoginEnterPassword`** — submit the password.
6. **`AccountDuplicationCheck`** — acknowledge.
7. **Conditional challenges** — `LoginAcid` (email/phone confirmation code),
   `LoginTwoFactorAuthChallenge` (TOTP/2FA). These are why headless
   username/password automation is unreliable.
8. On success the response carries the `auth_token` + `ct0` cookies. Persist them;
   that session is now equivalent to a logged-in browser.

Headers throughout: `authorization: Bearer ...`, `x-guest-token`,
`x-twitter-active-user: yes`, `x-twitter-client-language: en`, and once `ct0`
exists, `x-csrf-token`.

Reference implementation of this exact chain:
[`trevorhobenshield/twitter-api-client/twitter/login.py`](https://github.com/trevorhobenshield/twitter-api-client/blob/main/twitter/login.py).

## 3. The anti-bot wall: `x-client-transaction-id`

Since 2024 X gates many endpoints (including login subtasks and `CreateTweet`)
behind a **`x-client-transaction-id`** header, plus `x-xp-forwarded-for`. These
are generated client-side:

- `x-client-transaction-id` is derived from the **HTTP method + request path**
  combined with dynamic values parsed out of the homepage HTML and X's animated
  SVG/JS (an on-page key + animation frames feed a hashing routine).
- `x-xp-forwarded-for` encodes a browser-environment fingerprint (user agent,
  active-user flag, webdriver detection, guest-id cookie) under a derived key.

Because the inputs come from live page assets, you either (a) compute them with a
port of X's generator, or (b) let a real browser produce them. This scaffold
takes path (b) — the browser does the work — which sidesteps the hardest part of
the reverse-engineering effort.

Reference / writeup of the header generation:
[`glizzykingdreko/twitter-generator`](https://github.com/glizzykingdreko/twitter-generator).

## 4. Posting: the `CreateTweet` GraphQL mutation

Authenticated writes hit X's internal GraphQL gateway:

```
POST https://x.com/i/api/graphql/<queryId>/CreateTweet
# observed queryId (drifts): 7TKRKCPuAGsmYde0CudbVg
```

Request body shape:

```jsonc
{
  "variables": {
    "tweet_text": "hello world",
    "dark_request": false,
    "media": { "media_entities": [], "possibly_sensitive": false },
    "semantic_annotation_ids": []
    // reply:  "reply": { "in_reply_to_tweet_id": "<id>", "exclude_reply_user_ids": [] }
    // quote:  "attachment_url": "https://x.com/<user>/status/<id>"
  },
  "features": { /* ~30 responsive_web_* / longform_notetweets_* boolean flags */ },
  "queryId": "7TKRKCPuAGsmYde0CudbVg"
}
```

Headers: the bearer, `x-csrf-token` (= `ct0`), the `auth_token`/`ct0` cookies,
`content-type: application/json`, and the `x-client-transaction-id` from §3.
The `features` map must match what the current web client sends or X rejects the
call; treat both `queryId` and `features` as values to re-scrape periodically.

Related write operations follow the same pattern with different query ids:
`FavoriteTweet` (like), `CreateRetweet`, `DeleteTweet`, and the v1.1 REST
`friendships/create.json` (follow).

Reference: [`trevorhobenshield/twitter-api-client`](https://github.com/trevorhobenshield/twitter-api-client)
(`twitter/account.py` for `tweet()`, `twitter/constants.py` for `Operation.CreateTweet`
and `default_features`).

## 5. Why this scaffold stays on the browser for now

| | Browser DOM (current) | Direct GraphQL (future) |
| --- | --- | --- |
| `x-client-transaction-id` | produced for free by the page | must be ported / generated |
| Login challenges (2FA, email) | human solves them in the visible window | must be automated, brittle |
| Selector / queryId drift | data-testid selectors | queryId + features map |
| Speed / footprint | heavy (a real Chrome) | light (plain HTTP) |
| Detection surface | low (Patchright is undetected) | higher without the transaction id |

The pragmatic path: ship browser-driven write actions now, keep cookie auth as
the fast path, and migrate `post_tweet`/`reply`/`like`/`follow` to the GraphQL
endpoints above once a transaction-id generator is in place.

## Sources

- [trevorhobenshield/twitter-api-client](https://github.com/trevorhobenshield/twitter-api-client) — reverse-engineered v1.1/v2/GraphQL client (login flow + CreateTweet)
- [twitter-api-client/twitter/login.py](https://github.com/trevorhobenshield/twitter-api-client/blob/main/twitter/login.py) — the onboarding/task.json subtask chain
- [glizzykingdreko/twitter-generator](https://github.com/glizzykingdreko/twitter-generator) — `x-client-transaction-id` / `x-xp-forwarded-for` analysis
- [Manu's "DIY Twitter API"](https://unam.re/blog/developing-your-own-twitter-api) — guest token + onboarding walkthrough with Burp
- [Show HN: Twitter API Reverse Engineered](https://news.ycombinator.com/item?id=35548778) — discussion / context
- [fa0311/TwitterInternalAPIDocument](https://github.com/fa0311/TwitterInternalAPIDocument) — community catalog of GraphQL query ids and features
