"""
Unofficial X (Twitter) search ingestion via browser automation.

X's terms and technical barriers (login walls, bot checks, DOM changes) mean this
can break without notice. Use logged-in session cookies and run at modest volume.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import urllib.request

from crawler.envutil import env_float, env_int
from crawler.models import RawPost


_STATUS_PATH = re.compile(r"/@?([^/]+)/status/(\d+)")
_VIDEO_CDN = re.compile(r"https://video\.twimg\.com/.+\.(?:mp4|m3u8)")
_VIDEO_BROAD = re.compile(r"https://[a-z]+\.twimg\.com/[^\s\"]+\.mp4")
# Pattern to find mp4 URLs inside X GraphQL/API JSON responses
_MP4_IN_JSON = re.compile(r"https://video\.twimg\.com/[^\s\"\\]+\.mp4")


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


def _parse_articles(page: Any) -> list[dict[str, Any]]:
    """Extract tweet stubs from search results (text may be truncated)."""
    out: list[dict[str, Any]] = []
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

        show_more = art.query_selector('[data-testid="tweet-text-show-more-link"]')
        if not show_more:
            show_more = art.query_selector('a[href$="/status/' + tid + '"][role="link"]')

        has_video = art.query_selector("video") is not None or \
                    art.query_selector('[data-testid="videoPlayer"]') is not None

        out.append({
            "id": tid,
            "text": text,
            "created_at": created,
            "username": user.lstrip("@"),
            "truncated": show_more is not None,
            "has_video": has_video,
        })
    return out


def _fetch_video_via_syndication(tid: str) -> str | None:
    """Use X's syndication API to get the video URL — no browser needed."""
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&lang=en&token=0"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except Exception:  # noqa: BLE001
        return None

    # Look in mediaDetails for video variants
    best_url: str | None = None
    best_bitrate = 0
    for media in data.get("mediaDetails", []):
        if media.get("type") != "video":
            continue
        for variant in media.get("video_info", {}).get("variants", []):
            if variant.get("content_type") != "video/mp4":
                continue
            bitrate = variant.get("bitrate", 0) or 0
            if bitrate > best_bitrate:
                best_bitrate = bitrate
                best_url = variant.get("url")

    # Also check top-level "video" field
    if not best_url:
        video = data.get("video", {})
        for variant in video.get("variants", []):
            if variant.get("type") == "video/mp4" or ".mp4" in variant.get("src", ""):
                best_url = variant.get("src")
                break

    return best_url


def _pick_best_video(urls: list[str]) -> str | None:
    """From a list of X CDN video URLs, pick the highest resolution."""
    if not urls:
        return None
    # X CDN URLs contain resolution hints like /vid/avc1/1280x720/
    # Pick the one with the largest dimensions.
    def _res_score(u: str) -> int:
        m = re.search(r"/(\d{3,4})x(\d{3,4})/", u)
        if m:
            return int(m.group(1)) * int(m.group(2))
        return len(u)  # fallback: longer URL ≈ higher res
    return max(urls, key=_res_score)


_MAX_REPLIES = 5


def _try_trigger_video(page: Any, captured: list[str]) -> None:
    """Multiple strategies to trigger video playback and capture the URL."""
    if captured:
        return

    # Strategy 1: click the videoPlayer overlay / play button
    for selector in (
        '[data-testid="videoPlayer"]',
        '[data-testid="videoPlayer"] button',
        '[data-testid="videoComponent"]',
        '[aria-label="Play"]',
        '[aria-label="Play video"]',
        'button[aria-label*="lay"]',
    ):
        btn = page.query_selector(selector)
        if btn:
            try:
                btn.click(timeout=2000)
                page.wait_for_timeout(2000)
                if captured:
                    return
            except Exception:  # noqa: BLE001
                pass

    # Strategy 2: click the <video> element directly
    vid = page.query_selector("video")
    if vid:
        try:
            vid.click(timeout=2000)
            page.wait_for_timeout(2000)
            if captured:
                return
        except Exception:  # noqa: BLE001
            pass

    # Strategy 3: use JS to force play any <video> element
    try:
        page.evaluate("""
            const v = document.querySelector('video');
            if (v) { v.muted = true; v.play().catch(() => {}); }
        """)
        page.wait_for_timeout(3000)
    except Exception:  # noqa: BLE001
        pass


def _extract_video_from_page(page: Any) -> str | None:
    """Fallback: try to extract video URL from <video> src or page content."""
    try:
        # Check <video> element's src or currentSrc
        src = page.evaluate("""
            (() => {
                const v = document.querySelector('video');
                if (!v) return null;
                if (v.currentSrc && v.currentSrc.includes('.mp4')) return v.currentSrc;
                if (v.src && v.src.includes('.mp4')) return v.src;
                const source = v.querySelector('source[type="video/mp4"]');
                if (source) return source.src;
                return null;
            })()
        """)
        if src and ".mp4" in src and "blob:" not in src:
            return src
    except Exception:  # noqa: BLE001
        pass
    return None


def _fetch_tweet_detail(
    page: Any, username: str, tid: str
) -> tuple[str | None, str | None, list[str]]:
    """Navigate to an individual tweet page.
    Returns (full_text, best_video_url, reply_texts)."""
    captured_videos: list[str] = []

    def _on_response(response: Any) -> None:
        try:
            url = response.url
            # Direct CDN video URLs
            if _VIDEO_CDN.match(url) or _VIDEO_BROAD.match(url):
                captured_videos.append(url)
                return
            # X GraphQL/API responses contain video URLs in JSON body
            if ("api.x.com" in url or "twitter.com/i/api" in url) and response.status == 200:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    try:
                        body = response.text()
                        for m in _MP4_IN_JSON.findall(body):
                            cleaned = m.replace("\\u002F", "/").replace("\\/", "/")
                            captured_videos.append(cleaned)
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            pass

    page.on("response", _on_response)
    url = f"https://x.com/{username}/status/{tid}"
    text: str | None = None
    replies: list[str] = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3500)

        # Check if there's a video player on the page
        has_player = page.query_selector(
            '[data-testid="videoPlayer"], [data-testid="videoComponent"], video'
        )

        # Try to trigger video playback (multiple strategies)
        if has_player and not captured_videos:
            _try_trigger_video(page, captured_videos)

        # Scroll to load replies
        page.evaluate("window.scrollBy(0, 600)")
        page.wait_for_timeout(1500)

        all_text_els = page.query_selector_all('[data-testid="tweetText"]')
        if all_text_els:
            text = all_text_els[0].inner_text().strip() or None

        for el in all_text_els[1 : 1 + _MAX_REPLIES]:
            candidate = el.inner_text().strip()
            if candidate and len(candidate) > 20:
                replies.append(candidate)

        # If we still don't have a video URL, try extracting from the DOM
        if not captured_videos and has_player:
            direct = _extract_video_from_page(page)
            if direct:
                captured_videos.append(direct)

    except Exception as exc:  # noqa: BLE001
        print(f"X scrape: failed to fetch detail for {tid}: {exc}", flush=True)
    finally:
        try:
            page.remove_listener("response", _on_response)
        except Exception:  # noqa: BLE001
            pass

    # Last resort: syndication API (works without browser rendering)
    video = _pick_best_video(captured_videos)
    if not video:
        video = _fetch_video_via_syndication(tid)

    return text, video, replies


def backfill_video_urls(
    prompts: list[dict[str, Any]],
    *,
    max_per_run: int = 100,
) -> int:
    """Fetch video URLs for prompts missing them via X's syndication API.
    No browser needed — fast and reliable."""
    to_backfill = [
        p for p in prompts
        if not p.get("video_url") and p.get("source_url", "").startswith("https://x.com/")
    ]
    if not to_backfill:
        return 0

    to_backfill = to_backfill[:max_per_run]
    print(f"Video backfill: checking {len(to_backfill)} tweets via syndication API…", flush=True)
    updated = 0

    for i, prompt in enumerate(to_backfill):
        url = prompt["source_url"]
        m = _STATUS_PATH.search(url)
        if not m:
            continue
        tid = m.group(2)
        video_url = _fetch_video_via_syndication(tid)
        if video_url:
            prompt["video_url"] = video_url
            updated += 1

        if (i + 1) % 20 == 0:
            print(f"  … {i + 1}/{len(to_backfill)} ({updated} captured)", flush=True)

    print(f"Video backfill: captured {updated}/{len(to_backfill)} videos.", flush=True)
    return updated


def scrape_x_searches(
    queries: list[str],
    *,
    max_scrolls_per_query: int | None = None,
    pause_s: float | None = None,
    since: str | None = None,
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

    stubs: list[dict[str, Any]] = []
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

        # --- Phase 1: collect tweet stubs from search ---
        since_filter = f" since:{since}" if since else ""
        if since:
            print(f"X scrape: filtering posts since {since}", flush=True)
        login_wall = False
        for q in queries:
            if login_wall:
                break
            full_q = q + since_filter
            url = f"https://x.com/search?q={quote_plus(full_q)}&f=live&src=typed_query"
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
                for stub in _parse_articles(page):
                    if stub["id"] not in seen:
                        seen.add(stub["id"])
                        stubs.append(stub)
                page.evaluate("window.scrollBy(0, Math.floor(window.innerHeight * 2.1))")
                page.wait_for_timeout(int(pause * 1000))

        # --- Phase 2: visit individual tweet pages for full text + video + replies ---
        if stubs:
            print(
                f"X scrape: fetching details for {len(stubs)} posts "
                f"(text + video + replies)…",
                flush=True,
            )
        for i, stub in enumerate(stubs):
            full_text, video_url, replies = _fetch_tweet_detail(
                page, stub["username"], stub["id"]
            )
            if full_text and len(full_text) > len(stub["text"]):
                stub["text"] = full_text
            if video_url:
                stub["video_url"] = video_url
            if replies:
                stub["replies"] = replies
            if (i + 1) % 25 == 0:
                print(f"  … {i + 1}/{len(stubs)}", flush=True)

        context.close()
        browser.close()

    posts: list[RawPost] = []
    for s in stubs:
        posts.append(
            RawPost(
                id=f"x:{s['id']}",
                text=s["text"],
                created_at=s.get("created_at"),
                username=s["username"],
                source_url=f"https://x.com/{s['username']}/status/{s['id']}",
                network="x",
                metrics={},
                video_url=s.get("video_url"),
                replies=s.get("replies") or [],
            )
        )
    return posts
