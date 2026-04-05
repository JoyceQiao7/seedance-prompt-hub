"""Normalized post shape shared by all free-tier sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RawPost:
    """One public post from X, Bluesky, or Mastodon."""

    id: str
    text: str
    created_at: str | None
    username: str
    source_url: str
    network: str
    metrics: dict[str, Any]
    video_url: str | None = None
    replies: list[str] = field(default_factory=list)
