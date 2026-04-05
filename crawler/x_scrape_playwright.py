"""
Unofficial X (Twitter) search ingestion via browser automation.

X’s terms and technical barriers (login walls, bot checks, DOM changes) mean this
can break without notice. Use logged-in session cookies and run at modest volume.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from crawler.envutil import env_float, env_int
from crawler.models import RawPost


_STATUS_PATH = re.compile(r"/@?([^/]+)/status/(\d+)")


def _load_cookies() -> list[dict[str, Any]] | None:
    path = os.environ.get("X_COOKIES_PATH", "").strip()
    if not path:
        default = Path.cwd() / "x_cookies.json"
        if default.is_file():
            path = str(default)
    if path and Path(path).is_file():
        raw_file = Path(path).read_text(encoding="utf-8").strip()
        parsed = json.loads(raw_file)
        if isinstance(parsed, dict) and "cookies" in parsed:
            return list(parsed["cookies"])
        if isinstance(parsed, list):
            return parsed
    raw = os.environ.get("X_COOKIES_JSON", "").strip()
    if not raw:
        b64 = os.environ.get("X_COOKIES_B64", "").strip()
        if b64:
            import base64

            raw = base64.b64decode(b64).decode("utf-8")
    if not raw:
        return None
    parsed = json.loads(raw)
    if isinstance(parsed, dict) and "cookies" in parsed:
        return list(parsed["cookies"])
    if isinstance(parsed, list):
        return parsed
    return None


def _storage_state_path() -> str | None:
    p = os.environ.get("X_STORAGE_STATE_PATH", "").strip()
    if p and Path(p).is_file():
        return p
    return None


def _headless() -> bool:
    return os.environ.get("X_SCRAPE_HEADLESS", "1").lower() not in ("0", "false", "no")


def _looks_like_login_wall(page: Any) -> bool:
    u = page.url or ""
    if "/login" in u or "/i/flow/login" in u or "/i/flow/signup" in u:
        return True
    if page.query_selector('input[autocomplete="username"]'):
        return True
    return False


def _parse_articles(page: Any) -> list[RawPost]:
    out: list[RawPost] = []
    articles = page.query_selector_all('article[data-testid="tweet"]')
    for art in articles:
        link_el = art.query_selector('a[href*="/status/"]')
        if not link_el:
            continue
        href = link_el.get_attribute("href") or ""
        path = href.split("?")[0]
        m = _STATUS_PATH.search(path)
        if not m:
            continue
        user, tid = m.group(1), m.group(2)
        if user.lower() in ("i", "intent", "home", "search"):
            continue
        text_el = art.query_selector('[data-testid="tweetText"]')
        text = (text_el.inner_text() if text_el else "").strip()
        if not text:
            continue
        time_el = art.query_selector("time")
        created = time_el.get_attribute("datetime") if time_el else None
        out.append(
            RawPost(
                id=f"x:{tid}",
                text=text,
                created_at=created,
                username=user.lstrip("@"),
                source_url=f"https://x.com/{user.lstrip('@')}/status/{tid}",
                network="x",
                metrics={},
            )
        )
    return out


def scrape_x_searches(
    queries: list[str],
    *,
    max_scrolls_per_query: int | None = None,
    pause_s: float | None = None,
) -> list[RawPost]:
    from playwright.sync_api import sync_playwright

    cookies = _load_cookies()
    state_path = _storage_state_path()
    if not cookies and not state_path:
        print(
            "X scrape: no X_COOKIES_JSON / X_COOKIES_B64 / X_COOKIES_PATH / "
            "X_STORAGE_STATE_PATH — search is usually blocked. See README.",
            flush=True,
        )

    max_scrolls = max_scrolls_per_query or env_int("X_MAX_SCROLLS", 7)
    pause = pause_s if pause_s is not None else env_float("X_SCROLL_PAUSE", 1.8)
    initial_wait = int(env_float("X_SCRAPE_INITIAL_WAIT_MS", 4500.0))

    posts: list[RawPost] = []
    seen: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=_headless(),
            args=["--disable-blink-features=AutomationControlled"],
        )
        context_kwargs: dict[str, Any] = {
            "locale": "en-US",
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 900},
        }
        if state_path:
            context_kwargs["storage_state"] = state_path
        context = browser.new_context(**context_kwargs)
        if cookies and not state_path:
            context.add_cookies(cookies)
        page = context.new_page()

        login_wall = False
        for q in queries:
            if login_wall:
                break
            url = f"https://x.com/search?q={quote_plus(q)}&f=live&src=typed_query"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            except Exception as exc:  # noqa: BLE001
                print(f"X scrape: navigation failed for {q!r}: {exc}", flush=True)
                continue

            page.wait_for_timeout(initial_wait)
            if _looks_like_login_wall(page):
                print(
                    "X scrape: login wall — export cookies (auth_token + ct0) or "
                    "X_STORAGE_STATE_PATH from a logged-in Chromium profile.",
                    flush=True,
                )
                login_wall = True
                break

            for _ in range(max_scrolls):
                for raw in _parse_articles(page):
                    if raw.id not in seen:
                        seen.add(raw.id)
                        posts.append(raw)
                page.evaluate("window.scrollBy(0, Math.floor(window.innerHeight * 2.1))")
                page.wait_for_timeout(int(pause * 1000))

        context.close()
        browser.close()

    return posts
