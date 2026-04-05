"""Bluesky search via official AT Proto API ($0 with a free account + app password)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from crawler.models import RawPost


def _pds_base() -> str:
    return os.environ.get("BLUESKY_PDS_HOST", "https://bsky.social").rstrip("/")


def create_session(identifier: str, app_password: str) -> str:
    url = f"{_pds_base()}/xrpc/com.atproto.server.createSession"
    with httpx.Client(timeout=45.0) as client:
        r = client.post(
            url,
            json={"identifier": identifier.strip(), "password": app_password.strip()},
        )
        if r.status_code >= 400:
            raise RuntimeError(
                f"Bluesky login failed ({r.status_code}): check BLUESKY_IDENTIFIER and "
                "BLUESKY_APP_PASSWORD (use an App Password from Settings)."
            )
        return str(r.json()["accessJwt"])


def search_posts(
    access_jwt: str,
    query: str,
    *,
    max_pages: int = 4,
    per_page: int = 100,
) -> list[RawPost]:
    headers = {"Authorization": f"Bearer {access_jwt}"}
    out: list[RawPost] = []
    cursor: str | None = None
    base = _pds_base()

    with httpx.Client(timeout=60.0) as client:
        for _ in range(max_pages):
            params: dict[str, str | int] = {
                "q": query,
                "limit": min(per_page, 100),
            }
            if cursor:
                params["cursor"] = cursor

            r = client.get(
                f"{base}/xrpc/app.bsky.feed.searchPosts",
                headers=headers,
                params=params,
            )
            if r.status_code >= 400:
                raise RuntimeError(f"Bluesky search failed ({r.status_code}): {r.text[:200]}")

            payload = r.json()
            posts = payload.get("posts") or []
            for p in posts:
                norm = _normalize_post(p)
                if norm:
                    out.append(norm)

            cursor = payload.get("cursor")
            if not cursor:
                break

    return out


def _normalize_post(p: dict[str, Any]) -> RawPost | None:
    uri = p.get("uri")
    if not uri:
        return None
    author = p.get("author") or {}
    handle = author.get("handle") or "unknown"
    record = p.get("record") or {}
    text = (record.get("text") or "").strip()
    if not text:
        return None
    created = record.get("createdAt")
    rkey = str(uri).rsplit("/", 1)[-1]
    url = f"https://bsky.app/profile/{handle}/post/{rkey}"
    metrics = {
        "like_count": p.get("likeCount"),
        "repost_count": p.get("repostCount"),
        "reply_count": p.get("replyCount"),
    }
    return RawPost(
        id=f"bsky:{uri}",
        text=text,
        created_at=str(created) if created else None,
        username=str(handle),
        source_url=url,
        network="bluesky",
        metrics=metrics,
    )
