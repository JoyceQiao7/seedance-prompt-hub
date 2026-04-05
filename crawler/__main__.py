"""CLI: unofficial X search scrape → extract → internal screen → data/prompts.json."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

from crawler.categorize import categorize
from crawler.config import MIN_HEURISTIC_SCORE, X_SCRAPE_QUERIES
from crawler.envutil import env_int
from crawler.extract_prompt import extract_prompt
from crawler.merge_store import load_store, merge_items, save_store
from crawler.models import RawPost
from crawler.relevance import is_ai_video_creator_content
from crawler.screen import backfill_store_prompts, internal_screen
from crawler.score_quality import score_prompt
from crawler.x_scrape_playwright import scrape_x_searches


def _build_record(
    raw: RawPost,
    prompt_text: str,
    *,
    quality_score: int,
    category: str,
    screen: dict[str, Any],
) -> dict[str, Any]:
    author = raw.username if raw.username.startswith("@") else f"@{raw.username}"
    return {
        "id": raw.id,
        "text": prompt_text,
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


def _process_posts(raw_posts: list[RawPost]) -> list[dict[str, Any]]:
    incoming: list[dict[str, Any]] = []

    for raw in raw_posts:
        body = raw.text or ""
        if not is_ai_video_creator_content(body):
            continue
        extracted = extract_prompt(body)
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

    if os.environ.get("X_SKIP_SCRAPE", "").lower() in ("1", "true", "yes"):
        print("X_SKIP_SCRAPE set — skipping browser fetch.", flush=True)
        raw_posts: list[RawPost] = []
    else:
        print(f"X scrape: running {len(queries)} search queries (Latest).", flush=True)
        raw_posts = scrape_x_searches(queries)

    incoming = _process_posts(raw_posts)
    merged = merge_items(existing, incoming)
    force_backfill = os.environ.get("FORCE_SCREEN_BACKFILL", "").lower() in ("1", "true", "yes")
    n_back = backfill_store_prompts(merged, force=force_backfill)
    store["prompts"] = merged
    save_store(store)
    print(
        f"Stored {len(merged)} prompts ({len(incoming)} new screened this run from "
        f"{len(raw_posts)} scraped posts; backfill touched {n_back}).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
