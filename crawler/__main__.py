"""CLI entry: fetch from X, score, optionally LLM-review, merge into data/prompts.json."""

from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv

from crawler.categorize import categorize
from crawler.config import MAX_LLM_REVIEWS_PER_RUN, MIN_HEURISTIC_SCORE, SEARCH_QUERIES
from crawler.extract_prompt import extract_prompt
from crawler.merge_store import load_store, merge_items, save_store
from crawler.openai_review import review_prompt
from crawler.score_quality import score_prompt
from crawler.twitter_fetch import fetch_search_pages


def _build_record(
    tw: dict[str, Any],
    prompt_text: str,
    *,
    quality_score: int,
    category: str,
    reviewed_llm: bool,
) -> dict[str, Any]:
    username = tw.get("username") or "unknown"
    tweet_id = tw["id"]
    url = f"https://x.com/{username}/status/{tweet_id}"
    return {
        "id": tweet_id,
        "text": prompt_text,
        "category": category,
        "quality_score": quality_score,
        "source_url": url,
        "author": f"@{username}",
        "created_at": tw.get("created_at"),
        "tweet_text": tw.get("text"),
        "reviewed_llm": reviewed_llm,
        "likes": (tw.get("metrics") or {}).get("like_count"),
        "retweets": (tw.get("metrics") or {}).get("retweet_count"),
    }


def run() -> int:
    load_dotenv()
    bearer = os.environ.get("TWITTER_BEARER_TOKEN", "").strip()
    store = load_store()
    existing = list(store.get("prompts") or [])
    existing_ids = {p["id"] for p in existing if p.get("id")}

    incoming: list[dict[str, Any]] = []
    llm_used = 0

    if not bearer:
        print(
            "TWITTER_BEARER_TOKEN is not set; skipping X fetch. "
            "Merge-only run keeps existing data.",
            file=sys.stderr,
        )
    else:
        seen_tweet_ids: set[str] = set()
        raw_tweets: list[dict[str, Any]] = []
        for q in SEARCH_QUERIES:
            try:
                page = fetch_search_pages(bearer, q, max_pages=5)
            except Exception as exc:  # noqa: BLE001
                print(f"Query failed ({q[:48]}…): {exc}", file=sys.stderr)
                continue
            for tw in page:
                tid = tw.get("id")
                if tid and tid not in seen_tweet_ids:
                    seen_tweet_ids.add(tid)
                    raw_tweets.append(tw)

        for tw in raw_tweets:
            tweet_body = tw.get("text") or ""
            extracted = extract_prompt(tweet_body)
            if not extracted:
                continue
            heur = score_prompt(extracted)
            cat = categorize(extracted)
            reviewed_llm = False
            final_text = extracted
            final_score = heur
            final_cat = cat

            use_llm = (
                os.environ.get("OPENAI_API_KEY")
                and llm_used < MAX_LLM_REVIEWS_PER_RUN
                and tw["id"] not in existing_ids
                and heur >= MIN_HEURISTIC_SCORE
            )
            if use_llm:
                llm = review_prompt(tweet_body, extracted)
                llm_used += 1
                if llm and llm.get("keep"):
                    reviewed_llm = True
                    if llm.get("clean_prompt"):
                        final_text = llm["clean_prompt"]
                    final_cat = llm.get("category") or final_cat
                    q10 = int(llm.get("quality_10") or 5)
                    # Blend heuristic with LLM scale
                    final_score = int(round((heur * 0.45) + (q10 * 10 * 0.55)))
                    final_score = max(final_score, heur)
                elif llm and not llm.get("keep"):
                    continue

            if final_score < MIN_HEURISTIC_SCORE and not reviewed_llm:
                continue

            incoming.append(
                _build_record(
                    tw,
                    final_text,
                    quality_score=min(100, final_score),
                    category=final_cat,
                    reviewed_llm=reviewed_llm,
                )
            )

    merged = merge_items(existing, incoming)
    store["prompts"] = merged
    save_store(store)
    print(f"Stored {len(merged)} prompts ({len(incoming)} new/updated this run).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
