"""Read/write prompt store: full (private) vs public GitHub-facing export."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Keys allowed in the public repo / site bundle (no admin_feedback or other review-only fields).
PUBLIC_PROMPT_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "text",
        "display_text",
        "category",
        "quality_score",
        "source_url",
        "author",
        "created_at",
        "tweet_text",
        "source_network",
        "reviewed_llm",
        "likes",
        "retweets",
        "screen",
        "video_url",
        "thumbnail",
        "video",
        "published",
    }
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def public_data_path() -> Path:
    return repo_root() / "data" / "prompts.json"


def full_store_path() -> Path | None:
    """Path to the full store (published + unpublished + admin fields).

    - If ``PROMPTS_FULL_STORE`` is set (repo-relative or absolute), always use it.
    - Else if ``private/data/prompts.json`` exists, use it.
    - Else public-only mode (CI / fresh clones): no full store file.
    """
    env = os.environ.get("PROMPTS_FULL_STORE", "").strip()
    if env:
        p = Path(env)
        return p if p.is_absolute() else (repo_root() / p).resolve()
    default = repo_root() / "private" / "data" / "prompts.json"
    if default.is_file():
        return default.resolve()
    return None


def sanitize_prompt_for_public(p: dict[str, Any]) -> dict[str, Any] | None:
    if p.get("published") is not True:
        return None
    out: dict[str, Any] = {}
    for k in PUBLIC_PROMPT_KEYS:
        if k in p:
            out[k] = p[k]
    out["published"] = True
    return out


def export_public_store(store: dict[str, Any]) -> dict[str, Any]:
    prompts: list[dict[str, Any]] = []
    for p in store.get("prompts") or []:
        if not isinstance(p, dict):
            continue
        pub = sanitize_prompt_for_public(p)
        if pub:
            prompts.append(pub)
    return {"updated_at": store.get("updated_at") or _now_iso(), "prompts": prompts}


def write_public_prompts_json(store: dict[str, Any]) -> None:
    path = public_data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pub = export_public_store(store)
    with path.open("w", encoding="utf-8") as f:
        json.dump(pub, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_store() -> dict[str, Any]:
    full = full_store_path()
    if full is not None and full.is_file():
        with full.open(encoding="utf-8") as f:
            return json.load(f)
    path = public_data_path()
    if path.is_file():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": _now_iso(), "prompts": []}


def save_store(store: dict[str, Any]) -> None:
    store["updated_at"] = _now_iso()
    full = full_store_path()
    if full is not None:
        full.parent.mkdir(parents=True, exist_ok=True)
        with full.open("w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
            f.write("\n")
    write_public_prompts_json(store)


def apply_public_only_auto_publish(prompts: list[dict[str, Any]]) -> None:
    """CI / no-private-store: every row in the merged list should ship as visible on the site."""
    for p in prompts:
        if p.get("published") is not True:
            p["published"] = True


def _merge_prompt_record(prev: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Keep admin state and downloaded media when the crawler re-ingests the same tweet."""
    out = dict(incoming)
    if "published" in prev:
        out["published"] = prev["published"]
    if "admin_feedback" in prev:
        out["admin_feedback"] = prev["admin_feedback"]
    for key in ("video_url", "thumbnail", "video"):
        if not out.get(key) and prev.get(key):
            out[key] = prev[key]
    for key in ("likes", "retweets"):
        if out.get(key) is None and prev.get(key) is not None:
            out[key] = prev[key]
    return out


def merge_items(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {p["id"]: p for p in existing if p.get("id")}
    for p in incoming:
        pid = p.get("id")
        if not pid:
            continue
        prev = by_id.get(pid)
        if prev is None:
            by_id[pid] = p
        elif p.get("quality_score", 0) >= prev.get("quality_score", 0):
            by_id[pid] = _merge_prompt_record(prev, p)

    merged = list(by_id.values())
    merged.sort(
        key=lambda x: (
            x.get("quality_score", 0),
            x.get("created_at") or "",
        ),
        reverse=True,
    )
    return merged


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
