"""CLI: ingest from Bluesky + Mastodon ($0), optional X + OpenAI, merge into data/prompts.json."""

from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv

from crawler.bluesky_fetch import create_session, search_posts
from crawler.categorize import categorize
from crawler.config import (
    BLUESKY_SEARCH_QUERIES,
    MASTODON_INSTANCES,
    MASTODON_TAGS,
    MAX_LLM_REVIEWS_PER_RUN,
    MIN_HEURISTIC_SCORE,
    SEARCH_QUERIES,
)
from crawler.extract_prompt import extract_prompt
from crawler.mastodon_fetch import fetch_tag_timeline
from crawler.merge_store import load_store, merge_items, save_store
from crawler.models import RawPost
from crawler.openai_review import review_prompt
from crawler.relevance import is_seedance_related
from crawler.score_quality import score_prompt
from crawler.twitter_fetch import fetch_search_pages


def _raw_from_x(tw: dict[str, Any]) -> RawPost | None:
    tid = tw.get("id")
    if not tid:
        return None
    user = tw.get("username") or "unknown"
    text = tw.get("text") or ""
    return RawPost(
        id=f"x:{tid}",
        text=text,
        created_at=str(tw["created_at"]) if tw.get("created_at") else None,
        username=str(user),
        source_url=f"https://x.com/{user}/status/{tid}",
        network="x",
        metrics=dict(tw.get("metrics") or {}),
    )


def _collect_free_sources() -> list[RawPost]:
    """Bluesky + Mastodon: $0 automated feeds."""
    posts: list[RawPost] = []
    seen: set[str] = set()

    ident = os.environ.get("BLUESKY_IDENTIFIER", "").strip()
    app_pw = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if ident and app_pw:
        try:
            jwt = create_session(ident, app_pw)
            for q in BLUESKY_SEARCH_QUERIES:
                try:
                    for p in search_posts(jwt, q, max_pages=3):
                        if p.id not in seen:
                            seen.add(p.id)
                            posts.append(p)
                except Exception as exc:  # noqa: BLE001
                    print(f"Bluesky query failed ({q!r}): {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"Bluesky session failed: {exc}", file=sys.stderr)
    else:
        print(
            "Bluesky: set BLUESKY_IDENTIFIER + BLUESKY_APP_PASSWORD for $0 search ingest "
            "(see README).",
            file=sys.stderr,
        )

    mastodon_token = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip() or None
    for base in MASTODON_INSTANCES:
        for tag in MASTODON_TAGS:
            try:
                batch = fetch_tag_timeline(base, tag, limit=40, access_token=mastodon_token)
                for p in batch:
                    if p.id not in seen:
                        seen.add(p.id)
                        posts.append(p)
            except Exception as exc:  # noqa: BLE001
                print(f"Mastodon {base} #{tag}: {exc}", file=sys.stderr)

    return posts


def _collect_x_optional(bearer: str) -> list[RawPost]:
    if not bearer:
        return []
    seen: set[str] = set()
    out: list[RawPost] = []
    for q in SEARCH_QUERIES:
        try:
            page = fetch_search_pages(bearer, q, max_pages=5)
        except RuntimeError as exc:
            msg = str(exc)
            print(f"X query failed ({q[:48]}…): {exc}", file=sys.stderr)
            if "402" in msg:
                print(
                    "X: stopping further X queries (search not available on this plan).",
                    file=sys.stderr,
                )
                break
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"X query failed ({q[:48]}…): {exc}", file=sys.stderr)
            continue
        for tw in page:
            raw = _raw_from_x(tw)
            if raw and raw.id not in seen:
                seen.add(raw.id)
                out.append(raw)
    return out


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
        "retweets": raw.metrics.get("repost_count"),
    }


def _process_posts(
    raw_posts: list[RawPost],
    existing_ids: set[str],
) -> list[dict[str, Any]]:
    incoming: list[dict[str, Any]] = []
    llm_used = 0

    for raw in raw_posts:
        body = raw.text or ""
        if not is_seedance_related(body):
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

    bearer = os.environ.get("TWITTER_BEARER_TOKEN", "").strip()

    raw_posts: list[RawPost] = []
    raw_posts.extend(_collect_free_sources())
    raw_posts.extend(_collect_x_optional(bearer))

    if not bearer:
        print(
            "X: TWITTER_BEARER_TOKEN not set — skipping X (optional; often paid).",
            file=sys.stderr,
        )

    incoming = _process_posts(raw_posts, existing_ids)
    merged = merge_items(existing, incoming)
    store["prompts"] = merged
    save_store(store)
    print(
        f"Stored {len(merged)} prompts ({len(incoming)} accepted this run from "
        f"{len(raw_posts)} raw posts)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
