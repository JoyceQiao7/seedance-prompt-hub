"""Fetch recent posts from X API v2."""

from __future__ import annotations

from typing import Any

import httpx

TWITTER_SEARCH = "https://api.twitter.com/2/tweets/search/recent"


def fetch_search_pages(
    bearer: str,
    query: str,
    *,
    max_pages: int = 8,
) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {bearer}"}
    params: dict[str, str | int] = {
        "query": query,
        "max_results": 100,
        "tweet.fields": "created_at,author_id,public_metrics,lang,text",
        "expansions": "author_id",
        "user.fields": "username,name",
    }

    out: list[dict[str, Any]] = []
    next_token: str | None = None

    with httpx.Client(timeout=60.0) as client:
        for _ in range(max_pages):
            if next_token:
                params["next_token"] = next_token
            elif "next_token" in params:
                del params["next_token"]

            resp = client.get(TWITTER_SEARCH, headers=headers, params=params)
            if resp.status_code == 401:
                raise RuntimeError("X API returned 401: check TWITTER_BEARER_TOKEN.")
            if resp.status_code == 403:
                raise RuntimeError(
                    "X API returned 403: this app may need Elevated access for recent search."
                )
            if resp.status_code == 402:
                raise RuntimeError(
                    "X API returned 402 Payment Required: recent search is not on your plan."
                )
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data") or []
            includes = payload.get("includes") or {}
            users = {u["id"]: u for u in includes.get("users", [])}

            for tw in data:
                uid = tw.get("author_id")
                user = users.get(uid, {})
                out.append(
                    {
                        "id": tw["id"],
                        "text": tw.get("text") or "",
                        "created_at": tw.get("created_at"),
                        "username": user.get("username"),
                        "name": user.get("name"),
                        "metrics": tw.get("public_metrics") or {},
                    }
                )

            meta = payload.get("meta") or {}
            next_token = meta.get("next_token")
            if not next_token:
                break

    return out
