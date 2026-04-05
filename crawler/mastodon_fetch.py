"""Mastodon public hashtag timelines ($0; optional token if an instance requires it)."""

from __future__ import annotations

import os
import re
from html import unescape
from typing import Any
from urllib.parse import urlparse

import httpx

from crawler.models import RawPost


def _strip_html(html: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return unescape(t).strip()


def fetch_tag_timeline(
    instance_base: str,
    hashtag: str,
    *,
    limit: int = 40,
    access_token: str | None = None,
) -> list[RawPost]:
    """GET /api/v1/timelines/tag/:hashtag — works unauthenticated on many instances."""

    base = instance_base.rstrip("/")
    tag = hashtag.lstrip("#").lower()
    url = f"{base}/api/v1/timelines/tag/{tag}"
    headers: dict[str, str] = {}
    token = (access_token or os.environ.get("MASTODON_ACCESS_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {"limit": min(limit, 40)}
    host = urlparse(base).hostname or "unknown"

    with httpx.Client(timeout=45.0) as client:
        r = client.get(url, headers=headers, params=params)

    if r.status_code == 401 or r.status_code == 403:
        return []
    if r.status_code >= 400:
        raise RuntimeError(f"Mastodon {host} tag #{tag} failed ({r.status_code})")

    statuses = r.json()
    if not isinstance(statuses, list):
        return []

    out: list[RawPost] = []
    for st in statuses:
        norm = _normalize_status(st, host)
        if norm:
            out.append(norm)
    return out


def _normalize_status(st: dict[str, Any], host: str) -> RawPost | None:
    sid = st.get("id")
    if sid is None:
        return None
    html = st.get("content") or ""
    text = _strip_html(html)
    if not text:
        return None
    acct = (st.get("account") or {}).get("acct") or "unknown"
    url = st.get("url") or ""
    if not url:
        url = f"https://{host}/@{acct.split('@')[0]}/{sid}"
    metrics = {
        "like_count": st.get("favourites_count"),
        "repost_count": st.get("reblogs_count"),
    }
    return RawPost(
        id=f"m:{host}:{sid}",
        text=text,
        created_at=str(st.get("created_at")) if st.get("created_at") else None,
        username=str(acct),
        source_url=str(url),
        network="mastodon",
        metrics=metrics,
    )
