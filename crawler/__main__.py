"""CLI: unofficial X search scrape → extract/score → data/prompts.json."""

from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv

from crawler.categorize import categorize
from crawler.config import MAX_LLM_REVIEWS_PER_RUN, MIN_HEURISTIC_SCORE, X_SCRAPE_QUERIES
from crawler.extract_prompt import extract_prompt
from crawler.merge_store import load_store, merge_items, save_store
from crawler.models import RawPost
from crawler.openai_review import review_prompt
from crawler.relevance import is_ai_video_creator_content
from crawler.score_quality import score_prompt
from crawler.x_scrape_playwright import scrape_x_searches


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    return int(raw)


def _build_record(
    raw: RawPost,
    prompt_text: str,
    *,
    quality_score: int,
    category: str,
    reviewed_llm: bool,
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
        "reviewed_llm": reviewed_llm,
        "likes": raw.metrics.get("like_count"),
        "retweets": raw.metrics.get("retweet_count"),
    }


def _process_posts(
    raw_posts: list[RawPost],
    existing_ids: set[str],
) -> list[dict[str, Any]]:
    incoming: list[dict[str, Any]] = []
    llm_used = 0

    for raw in raw_posts:
        body = raw.text or ""
        if not is_ai_video_creator_content(body):
            continue
        extracted = extract_prompt(body)
        if not extracted:
            continue
        heur = score_prompt(extracted)
        cat = categorize(extracted)
        reviewed_llm = False
        final_text = extracted
        final_score = heur
        final_cat = cat

        use_llm = (
            bool(os.environ.get("OPENAI_API_KEY"))
            and llm_used < MAX_LLM_REVIEWS_PER_RUN
            and raw.id not in existing_ids
            and heur >= MIN_HEURISTIC_SCORE
        )
        if use_llm:
            llm = review_prompt(body, extracted)
            llm_used += 1
            if llm and llm.get("keep"):
                reviewed_llm = True
                if llm.get("clean_prompt"):
                    final_text = llm["clean_prompt"]
                final_cat = llm.get("category") or final_cat
                q10 = int(llm.get("quality_10") or 5)
                final_score = int(round((heur * 0.45) + (q10 * 10 * 0.55)))
                final_score = max(final_score, heur)
            elif llm and not llm.get("keep"):
                continue

        if final_score < MIN_HEURISTIC_SCORE and not reviewed_llm:
            continue

        incoming.append(
            _build_record(
                raw,
                final_text,
                quality_score=min(100, final_score),
                category=final_cat,
                reviewed_llm=reviewed_llm,
            )
        )

    return incoming


def run() -> int:
    load_dotenv()
    store = load_store()
    existing = list(store.get("prompts") or [])
    existing_ids = {p["id"] for p in existing if p.get("id")}

    max_queries = max(1, _env_int("X_MAX_QUERIES", 10))
    queries = X_SCRAPE_QUERIES[:max_queries]

    print(f"X scrape: running {len(queries)} search queries (Latest).", flush=True)
    raw_posts = scrape_x_searches(queries)

    incoming = _process_posts(raw_posts, existing_ids)
    merged = merge_items(existing, incoming)
    store["prompts"] = merged
    save_store(store)
    print(
        f"Stored {len(merged)} prompts ({len(incoming)} accepted this run from "
        f"{len(raw_posts)} scraped posts).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
