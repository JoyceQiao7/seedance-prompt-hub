"""Read/write prompt store: single canonical ``data/prompts.json`` (local == GitHub)."""

from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

_WS_COLLAPSE = re.compile(r"\s+")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def prompt_store_path() -> Path:
    """Path to ``data/prompts.json`` (published and unpublished rows; ``published`` per row)."""
    return repo_root() / "data" / "prompts.json"


def _mirror_prompts_to_web_public(data_path: Path) -> None:
    """Copy ``data/prompts.json`` to ``web/public/prompts.json`` when that tree exists."""
    web = repo_root() / "web" / "public" / "prompts.json"
    if web.parent.is_dir():
        shutil.copy2(data_path, web)


def write_prompts_json(store: dict[str, Any]) -> None:
    """Write the full store to ``data/prompts.json`` and mirror to ``web/public`` when present."""
    path = prompt_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
        f.write("\n")
    _mirror_prompts_to_web_public(path)


def load_store() -> dict[str, Any]:
    path = prompt_store_path()
    if path.is_file():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": _now_iso(), "prompts": []}


def save_store(store: dict[str, Any]) -> None:
    store["updated_at"] = _now_iso()
    write_prompts_json(store)


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


# --- Near-duplicate prompt bodies (crawl ingest) ---


def normalize_prompt_for_dedupe(text: str) -> str:
    """Lowercase, Unicode-normalize, collapse whitespace for comparison."""
    s = unicodedata.normalize("NFKC", text or "")
    return _WS_COLLAPSE.sub(" ", s.strip().lower())


def _similar_enough(a: str, b: str, threshold: float) -> bool:
    if not a or not b:
        return False
    la, lb = len(a), len(b)
    shorter, longer = (a, b) if la <= lb else (b, a)
    if len(shorter) >= 50 and shorter in longer:
        return True
    mx = max(la, lb)
    if mx < 80:
        return False
    if abs(la - lb) / mx > 0.22:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


class PromptDeduper:
    """Exact + fuzzy duplicate detection using existing prompts and in-run additions."""

    def __init__(
        self,
        existing_prompts: list[dict],
        *,
        similarity_threshold: float = 0.93,
        fuzzy: bool = True,
        min_chars: int = 24,
    ) -> None:
        self._similarity = similarity_threshold
        self._fuzzy = fuzzy
        self._min = min_chars
        self._exact: set[str] = set()
        self._corpus: list[str] = []
        for p in existing_prompts:
            if not isinstance(p, dict):
                continue
            for key in ("text", "display_text"):
                t = p.get(key)
                if isinstance(t, str) and t.strip():
                    self._index_text(t)

    @classmethod
    def from_env(cls, existing_prompts: list[dict]) -> PromptDeduper:
        raw = (os.environ.get("X_DEDUPE_SIMILARITY") or "").strip()
        threshold = float(raw) if raw else 0.93
        fuzzy = os.environ.get("X_DEDUPE_FUZZY", "1").lower() not in ("0", "false", "no")
        min_c = int(os.environ.get("X_DEDUPE_MIN_CHARS") or "24")
        return cls(existing_prompts, similarity_threshold=threshold, fuzzy=fuzzy, min_chars=min_c)

    def _index_text(self, text: str) -> None:
        n = normalize_prompt_for_dedupe(text)
        if len(n) < self._min:
            return
        self._exact.add(n)
        self._corpus.append(n)

    def is_duplicate(self, prompt_text: str) -> bool:
        n = normalize_prompt_for_dedupe(prompt_text)
        if len(n) < self._min:
            return False
        if n in self._exact:
            return True
        if not self._fuzzy:
            return False
        for other in self._corpus:
            if _similar_enough(n, other, self._similarity):
                return True
        return False

    def remember(self, prompt_text: str) -> None:
        """Record a prompt accepted this run so later items in the same batch dedupe against it."""
        self._index_text(prompt_text)
