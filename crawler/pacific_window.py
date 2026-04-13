"""Optional Pacific (America/Los_Angeles) inclusive date window for crawls."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

_PT = ZoneInfo("America/Los_Angeles")


def pst_window_utc_from_env() -> tuple[datetime, datetime] | None:
    """If ``X_PST_START`` and ``X_PST_END`` are set (YYYY-MM-DD), return UTC bounds inclusive of both local days."""
    start_s = (os.environ.get("X_PST_START") or "").strip()[:10]
    end_s = (os.environ.get("X_PST_END") or "").strip()[:10]
    if not start_s or not end_s:
        return None
    d0 = date.fromisoformat(start_s)
    d1 = date.fromisoformat(end_s)
    start_local = datetime.combine(d0, time.min, tzinfo=_PT)
    end_local = datetime.combine(d1, time(23, 59, 59, 999_999), tzinfo=_PT)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def parse_tweet_created_at(created_at: str | None) -> datetime | None:
    if not created_at or not str(created_at).strip():
        return None
    s = str(created_at).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def tweet_in_utc_window(
    created_at: str | None,
    utc_start: datetime,
    utc_end: datetime,
    *,
    include_if_missing_timestamp: bool = False,
) -> bool:
    """Return True if tweet time is within [utc_start, utc_end] (inclusive), both timezone-aware UTC."""
    dt = parse_tweet_created_at(created_at)
    if dt is None:
        return include_if_missing_timestamp
    return utc_start <= dt <= utc_end
