"""CLI: unofficial X search scrape → extract → internal screen → store + public export."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

from crawler.categorize import categorize
from crawler.config import MIN_HEURISTIC_SCORE, X_SCRAPE_QUERIES
from crawler.envutil import env_int
from crawler.extract_prompt import extract_prompt
from crawler.media import process_prompts_media
from crawler.merge_store import (
    apply_public_only_auto_publish,
    full_store_path,
    load_store,
    merge_items,
    save_store,
)
from crawler.models import RawPost
from crawler.prompt_trimmer import trim_to_prompt_body
from crawler.relevance import is_ai_video_creator_content
from crawler.screen import backfill_store_prompts, internal_screen
from crawler.screen_rules import post_matches_off_target_memory
from crawler.score_quality import score_prompt
from crawler.x_scrape_playwright import backfill_video_urls, scrape_x_searches


def _build_record(
    raw: RawPost,
    prompt_text: str,
    *,
    quality_score: int,
    category: str,
    screen: dict[str, Any],
) -> dict[str, Any]:
    author = raw.username if raw.username.startswith("@") else f"@{raw.username}"
    rec: dict[str, Any] = {
        "id": raw.id,
        "text": prompt_text,
        "display_text": trim_to_prompt_body(prompt_text),
        "category": category,
        "quality_score": quality_score,
        "source_url": raw.source_url,
        "author": author,
        "created_at": raw.created_at,
        "tweet_text": raw.text,
        "source_network": raw.network,
        "reviewed_llm": False,
        "likes": raw.metrics.get("like_count"),
        "retweets": raw.metrics.get("retweet_count"),
        "screen": screen,
    }
    if raw.video_url:
        rec["video_url"] = raw.video_url
    return rec


def _best_prompt_text(raw: RawPost) -> str | None:
    """Pick the best prompt source: main text or any of the replies."""
    body = raw.text or ""
    extracted = extract_prompt(body)
    best = extracted
    best_score = score_prompt(extracted) if extracted else 0

    for reply in raw.replies:
        reply_extracted = extract_prompt(reply)
        if not reply_extracted:
            continue
        reply_score = score_prompt(reply_extracted)
        if reply_score > best_score:
            best = reply_extracted
            best_score = reply_score

    return best


def _process_posts(raw_posts: list[RawPost]) -> list[dict[str, Any]]:
    incoming: list[dict[str, Any]] = []

    for raw in raw_posts:
        body = raw.text or ""
        combined_text = body + "\n" + "\n".join(raw.replies)
        if not is_ai_video_creator_content(combined_text):
            continue
        if post_matches_off_target_memory(body, combined_text):
            continue

        extracted = _best_prompt_text(raw)
        if not extracted:
            continue
        heur = score_prompt(extracted)
        cat = categorize(extracted)
        final_text = extracted
        final_score = heur
        final_cat = cat

        if final_score < MIN_HEURISTIC_SCORE:
            continue

        scr = internal_screen(final_text, body, legacy_quality=None)
        if not scr.approved:
            continue

        final_text = scr.prepared_text
        incoming.append(
            _build_record(
                raw,
                final_text,
                quality_score=min(100, final_score),
                category=final_cat,
                screen=scr.to_dict(),
            )
        )

    return incoming


def run() -> int:
    load_dotenv()
    store = load_store()
    existing = list(store.get("prompts") or [])
    max_queries = max(1, env_int("X_MAX_QUERIES", 10))
    queries = X_SCRAPE_QUERIES[:max_queries]

    # Use last crawl timestamp to only fetch new posts
    last_updated = store.get("updated_at", "")
    since_date: str | None = None
    if last_updated and not os.environ.get("X_FULL_CRAWL"):
        since_date = last_updated[:10]  # "2026-04-05T..." → "2026-04-05"

    if os.environ.get("X_SKIP_SCRAPE", "").lower() in ("1", "true", "yes"):
        print("X_SKIP_SCRAPE set — skipping browser fetch.", flush=True)
        raw_posts: list[RawPost] = []
    else:
        print(f"X scrape: running {len(queries)} search queries (Latest).", flush=True)
        raw_posts = scrape_x_searches(queries, since=since_date)

    incoming = _process_posts(raw_posts)
    merged = merge_items(existing, incoming)
    force_backfill = os.environ.get("FORCE_SCREEN_BACKFILL", "").lower() in ("1", "true", "yes")
    n_back = backfill_store_prompts(merged, force=force_backfill)

    # Backfill video URLs for prompts that are missing them
    skip_scrape = os.environ.get("X_SKIP_SCRAPE", "").lower() in ("1", "true", "yes")
    n_vid_backfill = 0
    if not skip_scrape:
        n_vid_backfill = backfill_video_urls(merged)

    skip_media = os.environ.get("SKIP_MEDIA", "").lower() in ("1", "true", "yes")
    n_media = 0
    if not skip_media:
        n_media = process_prompts_media(merged)

    _full = full_store_path()
    if _full is None or not _full.is_file():
        apply_public_only_auto_publish(merged)

    store["prompts"] = merged
    save_store(store)
    print(
        f"Stored {len(merged)} prompts ({len(incoming)} new screened this run from "
        f"{len(raw_posts)} scraped posts; backfill touched {n_back}; "
        f"video backfill {n_vid_backfill}; media processed {n_media}).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
