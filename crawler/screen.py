"""Rule-based screening and light text prep — no external APIs."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from crawler.config import SCREEN_MIN_SCORE
from crawler.screen_rules import non_prompt_substrings
from crawler.score_quality import looks_spammy

_URL = re.compile(r"https?://\S+", re.I)
_PROMO = re.compile(
    r"(?i)(subscribe\s+to|link\s+in\s+bio|check\s+out\s+my|discount\s+code|"
    r"promo\s+code|use\s+code\s+\w+|buy\s+now|click\s+the\s+link)"
)
_REPEATED = re.compile(r"(.)\1{14,}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prepare_prompt_text(text: str) -> str:
    """Normalize whitespace and invisible characters for storage/display."""
    t = unicodedata.normalize("NFKC", text or "")
    t = t.replace("\u200b", "").replace("\ufeff", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t.strip())
    return t.strip()


@dataclass
class ScreenResult:
    approved: bool
    score: int
    reasons: list[str] = field(default_factory=list)
    prepared_text: str = ""
    hard_block: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "score": self.score,
            "reasons": self.reasons,
            "reviewed_at": _now_iso(),
            "engine": "internal_rules_v1",
        }


def internal_screen(
    prompt_text: str,
    source_post: str,
    *,
    legacy_quality: int | None = None,
) -> ScreenResult:
    """
    Decide if a prompt is fit to publish using heuristics only.
    `legacy_quality` relaxes rejection for older rows on first backfill.
    """
    prepared = prepare_prompt_text(prompt_text)
    reasons: list[str] = []
    hard_block = False
    score = 88

    combined = f"{prepared}\n{source_post or ''}"
    n = len(prepared)
    combined_lower = combined.lower()

    for sub in non_prompt_substrings():
        if sub.lower() in combined_lower:
            reasons.append("learned_non_prompt_marker")
            hard_block = True
            score -= 80
            break

    if looks_spammy(combined):
        reasons.append("spam_pattern")
        hard_block = True
        score -= 80

    if _PROMO.search(combined):
        reasons.append("promo_language")
        score -= 35

    if n < 32:
        reasons.append("too_short")
        hard_block = True
        score -= 50
    elif n < 48:
        reasons.append("short")
        score -= 18

    if n > 3600:
        reasons.append("very_long")
        score -= 12

    url_n = len(_URL.findall(prepared))
    if url_n > 2:
        reasons.append("too_many_urls")
        score -= min(40, url_n * 12)

    hc, ac = prepared.count("#"), prepared.count("@")
    if hc > 10:
        reasons.append("hashtag_noise")
        score -= min(30, (hc - 10) * 3)
    if ac > 8:
        reasons.append("mention_noise")
        score -= min(24, (ac - 8) * 3)

    if _REPEATED.search(prepared):
        reasons.append("repeated_characters")
        score -= 25

    letters = sum(1 for c in prepared if c.isalpha())
    if n > 60 and letters / max(n, 1) < 0.35:
        reasons.append("low_letter_ratio")
        score -= 22

    if not re.search(r"[a-zA-Z]{4,}", prepared):
        reasons.append("few_words")
        hard_block = True
        score -= 40

    score = max(0, min(100, score))

    approved = score >= SCREEN_MIN_SCORE and not hard_block

    if (
        not approved
        and legacy_quality is not None
        and not hard_block
        and not looks_spammy(combined)
        and legacy_quality >= 55
        and n >= 40
    ):
        approved = True
        reasons.append("legacy_quality_pass")

    reasons_u = sorted(set(reasons))
    return ScreenResult(
        approved=approved,
        score=score,
        reasons=reasons_u,
        prepared_text=prepared,
        hard_block=hard_block,
    )


def backfill_store_prompts(prompts: list[dict[str, Any]], *, force: bool = False) -> int:
    """Attach `screen` to rows missing it (or all rows if force). Returns count updated."""
    changed = 0
    for p in prompts:
        if not force and p.get("screen"):
            continue
        text = (p.get("text") or "").strip()
        post = (p.get("tweet_text") or "") or ""
        if not text:
            continue
        lq_raw = p.get("quality_score")
        legacy = int(lq_raw) if lq_raw is not None else None
        legacy_use = None if force else legacy
        res = internal_screen(text, post, legacy_quality=legacy_use)
        p["text"] = res.prepared_text
        p["screen"] = res.to_dict()
        changed += 1
    return changed
