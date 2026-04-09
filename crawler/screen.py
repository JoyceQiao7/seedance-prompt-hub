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

# Thread / truncation cues — extracted prompt should not ship looking cut off.
_INCOMPLETE_BODY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?i)\bcontinued\s+(?:in|on)\s+(?:the\s+)?(?:thread|comments|replies)\b"
        ),
        "continued_elsewhere",
    ),
    (
        re.compile(
            r"(?i)\bfull\s+(?:video\s+)?prompt\s+(?:in|on|below|above|comments|replies)\b"
        ),
        "full_prompt_elsewhere",
    ),
    (
        re.compile(r"(?i)\bsee\s+(?:my\s+)?(?:next\s+)?(?:tweet|thread|post|pin)\b"),
        "see_followup_post",
    ),
    (
        re.compile(r"(?i)\bread\s+more\s+(?:in|on|below|here)\b"),
        "read_more_elsewhere",
    ),
    (
        re.compile(
            r"(?i)\b(?:swipe|tap)\s+(?:to\s+)?(?:see|read|get)\s+(?:the\s+)?(?:full|rest)\b"
        ),
        "swipe_for_more",
    ),
    (
        re.compile(r"(?i)\bmore\s+in\s+(?:the\s+)?(?:thread|comments|replies)\b"),
        "more_in_thread",
    ),
    (
        re.compile(
            r"(?i)\bdetails\s+in\s+(?:the\s+)?(?:next\s+)?(?:post|tweet|thread)\b"
        ),
        "details_next_post",
    ),
    (
        re.compile(r"(?i)\bfind\s+the\s+rest\s+(?:of\s+)?(?:the\s+)?(?:story|prompt|thread)\b"),
        "find_rest_truncation",
    ),
    (
        re.compile(r"(?i)\b(?:story|prompt)\s+continues\s+(?:in|on)\b"),
        "story_continues_elsewhere",
    ),
    (re.compile(r"(?i)\bprompt\s+in\s+the\s+thread\b"), "prompt_in_thread"),
    (re.compile(r"(?i)\bin\s+the\s+thread\s+below\b"), "in_thread_below"),
    (re.compile(r"(?i)\bfull\s+.*\bprompt\s+in\s+the\s+thread\b"), "full_prompt_in_thread"),
]


def _structural_truncation_signals(prepared: str) -> list[str]:
    """Body looks cut mid-clause (crawler/UI truncation), not a deliberate teaser phrase."""
    sig: list[str] = []
    pt = prepared.strip()
    if len(pt) < 90:
        return sig

    if re.search(r",\s*$", pt):
        sig.append("truncated_trailing_comma")
    if len(pt) > 180 and re.search(r":\s*$", pt) and not re.search(
        r"(?i)\b(?:scene|camera|lighting|wave|step)\s*:\s*$", pt
    ):
        sig.append("truncated_trailing_colon")
    if re.search(r"[–—\-]\s*$", pt):
        sig.append("truncated_trailing_dash")

    o, c = pt.count("("), pt.count(")")
    if "(" in pt and o > c:
        sig.append("truncated_unclosed_paren")

    if re.search(
        r"(?i)\b(?:shallow\s+depth\s+of|prime\s+lens\s+for\s+a|tracking\s+forward\s+as\s+the)\s*$",
        pt,
    ):
        sig.append("truncated_mid_phrase_tail")

    if re.search(
        r"(?i)\b(?:high-speed|slow-motion|wide-angle|medium\s+shot|tracking\s+shot)\s*$",
        pt,
    ):
        sig.append("truncated_mid_compound_tail")

    if re.search(
        r"(?i)(?:^|\s)(?:of|with|for|to|from|in|at|by|as)\s*$",
        pt,
    ) and len(pt) > 120:
        sig.append("truncated_dangling_function_word")

    return sorted(set(sig))


def _incomplete_content_signals(prepared: str) -> list[str]:
    """Heuristics for thread fragments and 'go elsewhere for the rest' posts."""
    sig: list[str] = []
    pt = prepared.strip()
    if len(pt) < 28:
        return sig

    m = re.search(r"[\[\(]\s*(\d+)\s*/\s*(\d+)\s*[\]\)]\s*$", pt)
    if m and int(m.group(1)) < int(m.group(2)):
        sig.append("partial_thread_marker_tail")

    om = re.match(r"^\s*[\[(]\s*1\s*/\s*(\d+)\s*[\])]", pt)
    if om and int(om.group(1)) <= 10 and len(pt) < 800:
        # e.g. [1/3] thread opener; skip 1/15s-style timings (large denominator)
        sig.append("opens_thread_part_one_short")

    for pat, rid in _INCOMPLETE_BODY_PATTERNS:
        if pat.search(pt):
            sig.append(rid)

    return sorted(set(sig))


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

    inc = _incomplete_content_signals(prepared)
    if inc:
        reasons.extend(inc)
        # Auto-reject: these posts need a fuller fetch or are teasers, not copy-paste prompts.
        hard_block = True
        score -= min(80, 14 * len(inc))

    trunc = _structural_truncation_signals(prepared)
    if trunc:
        reasons.extend(trunc)
        hard_block = True
        score -= min(80, 12 * len(trunc))

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


def rescreen_pending_prompts(prompts: list[dict[str, Any]]) -> int:
    """Re-run internal_screen + trimmer on rows still awaiting admin (published is null).

    Does not change rows that are already published (True) or rejected (False).
    """
    from crawler.prompt_trimmer import trim_to_prompt_body

    changed = 0
    for p in prompts:
        if p.get("published") is not None:
            continue
        text = (p.get("text") or "").strip()
        post = (p.get("tweet_text") or "") or ""
        if not text:
            continue
        prepared = prepare_prompt_text(text)
        res = internal_screen(prepared, post, legacy_quality=None)
        p["text"] = prepared
        p["screen"] = res.to_dict()
        p["display_text"] = trim_to_prompt_body(prepared)
        changed += 1
    return changed


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
