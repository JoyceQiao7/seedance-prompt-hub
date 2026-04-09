"""Maintenance tasks: re-screen pending prompts, refresh X like counts via syndication.

Run from repo root::

    PYTHONPATH=. python -m crawler.maintain

Then sync the hub dataset::

    cd web && node scripts/sync-data.mjs
"""

from __future__ import annotations

from crawler.merge_store import load_store, save_store
from crawler.screen import rescreen_pending_prompts
from crawler.x_scrape_playwright import backfill_likes_from_syndication


def _published_or_pending_unset(p: dict) -> bool:
    """Published hub posts plus rows still in the admin queue (published null)."""
    pub = p.get("published")
    return pub is True or pub is None


def main() -> None:
    store = load_store()
    prompts = list(store.get("prompts") or [])
    n_screen = rescreen_pending_prompts(prompts)
    n_likes = backfill_likes_from_syndication(prompts, predicate=_published_or_pending_unset)
    store["prompts"] = prompts
    save_store(store)
    print(
        f"Done. Re-screened {n_screen} pending prompts; "
        f"like metrics refreshed for {n_likes} posts (published + pending).",
        flush=True,
    )


if __name__ == "__main__":
    main()
