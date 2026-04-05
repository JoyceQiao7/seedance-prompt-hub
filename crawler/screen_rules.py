"""Learned rules from admin \"off target\" feedback (no real prompt in the post).

Uses content only — never blocks authors. Teaches the crawler via:
- optional substrings the admin provides (appear in post → treat as non-prompt)
- fingerprints of posts marked off target (exact normalized tweet text → skip)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = _ROOT / "data" / "screen_rules.json"

_cache: dict[str, Any] | None = None

_MAX_FINGERPRINTS = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reload_screen_rules() -> None:
    global _cache
    _cache = None


def _normalize_tweet_for_fingerprint(s: str) -> str:
    t = (s or "").strip().lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tweet_fingerprint(s: str) -> str:
    """Short hash of normalized text; empty if too short to be reliable."""
    norm = _normalize_tweet_for_fingerprint(s)
    if len(norm) < 12:
        return ""
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


def load_screen_rules() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    if RULES_PATH.is_file():
        try:
            _cache = json.loads(RULES_PATH.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            _cache = {}
    else:
        _cache = {}

    # Defaults + migrate legacy keys
    if "non_prompt_substrings" not in _cache and _cache.get("reject_substrings"):
        _cache["non_prompt_substrings"] = list(_cache["reject_substrings"])
    if "non_prompt_substrings" not in _cache:
        _cache["non_prompt_substrings"] = []
    if "off_target_fingerprints" not in _cache:
        _cache["off_target_fingerprints"] = []
    if "feedback_log" not in _cache:
        _cache["feedback_log"] = []
    return _cache


def save_screen_rules(rules: dict[str, Any]) -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Drop legacy / unused keys on write
    out = {
        "non_prompt_substrings": rules.get("non_prompt_substrings", []),
        "off_target_fingerprints": rules.get("off_target_fingerprints", []),
        "feedback_log": rules.get("feedback_log", []),
    }
    with RULES_PATH.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    reload_screen_rules()


def non_prompt_substrings() -> list[str]:
    rules = load_screen_rules()
    raw = rules.get("non_prompt_substrings") or rules.get("reject_substrings") or []
    out = [str(s) for s in raw if s]
    return sorted(out, key=len, reverse=True)


def off_target_fingerprints() -> set[str]:
    rules = load_screen_rules()
    return {str(x) for x in rules.get("off_target_fingerprints", []) if x}


def text_has_non_prompt_marker(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    for sub in non_prompt_substrings():
        if sub.lower() in low:
            return True
    return False


def post_matches_off_target_memory(main_tweet_text: str, combined_text: str) -> bool:
    """True if this scraped post matches learned off-target content (fingerprints or markers)."""
    if text_has_non_prompt_marker(combined_text):
        return True
    fp_body = tweet_fingerprint(main_tweet_text)
    if fp_body and fp_body in off_target_fingerprints():
        return True
    return False


def learn_screen_rules_from_store(store: dict[str, Any]) -> int:
    """Merge off_target (and legacy low_quality) feedback into screen_rules.json.

    - Optional block_phrase (>= 8 chars) → non_prompt_substrings
    - Every off_target row → fingerprint of tweet_text / text (same post again = skip)

    Returns number of new substrings + new fingerprints added.
    """
    rules = load_screen_rules()
    prev_subs = {str(s) for s in rules.get("non_prompt_substrings", []) if s}
    legacy = {str(s) for s in rules.get("reject_substrings", []) if s}
    prev_subs |= legacy

    prev_fps = {str(x) for x in rules.get("off_target_fingerprints", []) if x}

    subs = set(prev_subs)
    fps = set(prev_fps)

    for p in store.get("prompts", []):
        fb = p.get("admin_feedback")
        if not fb or fb.get("action") != "reject":
            continue
        reason = fb.get("reason", "")
        if reason not in ("off_target", "low_quality"):
            continue

        bp = (fb.get("block_phrase") or "").strip()
        if len(bp) >= 8:
            subs.add(bp)

        src = (p.get("tweet_text") or p.get("text") or "").strip()
        fp = tweet_fingerprint(src)
        if fp:
            fps.add(fp)

    subs_sorted = sorted(subs, key=len, reverse=True)
    prev_subs_sorted = sorted(prev_subs, key=len, reverse=True)
    fps_sorted = sorted(fps)
    if len(fps_sorted) > _MAX_FINGERPRINTS:
        fps_sorted = fps_sorted[-_MAX_FINGERPRINTS:]
    prev_fps_sorted = sorted(prev_fps)

    if subs_sorted == prev_subs_sorted and fps_sorted == prev_fps_sorted:
        return 0

    delta_subs = len(subs) - len(prev_subs)
    delta_fps = len(fps) - len(prev_fps)
    new_total = max(0, delta_subs) + max(0, delta_fps)

    rules["non_prompt_substrings"] = subs_sorted
    rules["off_target_fingerprints"] = fps_sorted
    for k in ("reject_substrings", "blocked_authors"):
        rules.pop(k, None)

    log = list(rules.get("feedback_log", []))
    log.append(
        {
            "timestamp": _now_iso(),
            "new_non_prompt_substrings": delta_subs,
            "new_fingerprints": delta_fps,
        }
    )
    rules["feedback_log"] = log[-50:]
    save_screen_rules(rules)
    return new_total
