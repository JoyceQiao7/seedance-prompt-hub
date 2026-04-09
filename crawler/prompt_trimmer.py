"""Strip social-media preamble, commercial content, and trailing noise.

The trimmer operates in layers:
1. Tail noise      — thread spam, trailing #hashtag runs, promo tails.
2. Commercial      — known AI-video tool @handles, brand phrases, promo #tags
                     (whole lines/sentences removed when they only promote).
3. Learned rules   — data/trim_rules.json from admin feedback.
4. Label / preamble — extract the actual prompt body.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from crawler.promo_vocab import (
    AI_VIDEO_BRAND_PHRASES,
    AI_VIDEO_TOOL_HANDLES,
    PROMO_HASHTAG_STEMS,
)

# ── Paths ────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
_RULES_PATH = _ROOT / "data" / "trim_rules.json"

# Handles / brands — large seed list in promo_vocab; admin feedback extends handles.
_BUILTIN_COMMERCIAL_HANDLES: set[str] = set(AI_VIDEO_TOOL_HANDLES)
_BUILTIN_COMMERCIAL_BRANDS: set[str] = set(AI_VIDEO_BRAND_PHRASES)

# Exact-match-only hashtag stems (too ambiguous for prefix match).
_PROMO_HASHTAG_EXACT: frozenset[str] = frozenset(
    s for s in PROMO_HASHTAG_STEMS if len(s) <= 3
)
_PROMO_HASHTAG_PREFIX: frozenset[str] = frozenset(
    s for s in PROMO_HASHTAG_STEMS if len(s) > 3
)

# ── Learned rules cache ─────────────────────────────────────────────────────
_learned: dict[str, Any] | None = None


def _load_learned() -> dict[str, Any]:
    """Load learned rules from disk (cached after first call)."""
    global _learned
    if _learned is not None:
        return _learned
    if _RULES_PATH.is_file():
        try:
            _learned = json.loads(_RULES_PATH.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            _learned = {}
    else:
        _learned = {}
    return _learned


def reload_learned() -> None:
    """Force-reload learned rules (call after admin updates them)."""
    global _learned
    _learned = None
    _load_learned()


def _all_commercial_handles() -> set[str]:
    rules = _load_learned()
    extra = {h.lower().lstrip("@") for h in rules.get("commercial_handles", [])}
    return _BUILTIN_COMMERCIAL_HANDLES | extra


def _all_strip_phrases() -> list[str]:
    rules = _load_learned()
    return list(rules.get("strip_phrases", []))


def _all_protected_phrases() -> list[str]:
    rules = _load_learned()
    return list(rules.get("protected_phrases", []))


# ── Trailing noise (stripped FIRST so label-matching doesn't hit them) ───────
_TAIL_NOISE: list[re.Pattern[str]] = [
    re.compile(r"(?i)\.{3,}\s*Find the rest.*$", re.S),
    re.compile(r"(?i)\bFind the rest of.*$", re.S),
    re.compile(r"(?i)\bFind the rest\b.*$", re.S),
    re.compile(r"(?i)\bFollow (?:me|us|for)\b.*$", re.S),
    re.compile(r"(?i)\bLink in bio\b.*$", re.S),
    re.compile(r"(?i)\bSign up\b.*$", re.S),
    re.compile(r"(?i)\bGr[ea]ding\s*[:：]?\s*@\w+.*$", re.S),
    re.compile(r"(?i)\s*[—–-]\s*(?:made\s+)?(?:on|with|by|via)?\s*@\w+\s*$"),
    re.compile(r"(?:\s*@\w+){3,}\s*$"),
]

# One or more trailing social #hashtags (any tag); handled in _strip_trailing_hashtag_block.
_TRAILING_HASHTAG_RUN = re.compile(r"(?:\s+#[\w\u00c0-\u024f]+)+\s*$", re.UNICODE)
_LINE_ONLY_HASHTAGS = re.compile(
    r"^(?:#[\w\u00c0-\u024f]+)(?:\s+#[\w\u00c0-\u024f]+)*$",
    re.UNICODE,
)

# ── Prompt-label patterns ───────────────────────────────────────────────────
_LABEL_RE: list[re.Pattern[str]] = [
    re.compile(r"(?i)\b(?:full\s+)?prompt\s*[:：]\s*"),
    re.compile(r"\bPROMPT\s+"),
    re.compile(r"(?i)\bPrompt\s+(?:share|sharing)\s*[:：]?\s*"),
    re.compile(r"(?i)\bPromptShare\s*[:：]?\s+"),
    re.compile(r"(?i)\btext[- ]to[- ]video\s+prompt\s*[:：]?\s*"),
    re.compile(r"(?i)\b(?:seedance|sd)\s*2\.?0?\s+prompt\s*[:：]?\s*"),
    re.compile(r"(?i)プロンプト\s*[:：]?\s*"),
    re.compile(r"(?i)\bPrompt\s+(?=[A-Z\[\{\"*])"),
]

# Structural markers that signal the prompt body start.
_STRUCT_START = re.compile(
    r"(?m)^(?:"
    r"\[(?:CINEMATIC|SETUP|STYLE|SHOT|SCENE|TECHNICAL|DURATION|CAMERA|IMAGE)"
    r"|\*\*\w"
    r"|\{"
    r"|SHOT\s*:"
    r"|Scene\s*\d"
    r"|\d{1,2}\s*[–—-]\s*\d{1,2}\s*s\b"
    r")",
    re.I,
)

# Strong visual/cinematic sentence openers.
_VISUAL_CUE = re.compile(
    r"(?i)(?:^|\n)\s*"
    r"(?:"
    r"Ultra[- ]?\s*cinematic|Hyper[- ]?\s*realistic|Cinematic|Photorealistic|"
    r"Shot on|Generate\s+a|Create\s+a|"
    r"Handheld|Aerial|First[- ]person|POV|FPV|"
    r"Macro|Wide[- ]?angle|Close[- ]up|Medium[- ](?:shot|close)|Low[- ]angle|"
    r"Opening\s+frame|Establishing\s+shot|"
    r"Strictly\s+follow|"
    r"A\s+(?:towering|massive|tiny|young|old|lone|dark|bright|matte|sleek|luxury)|"
    r"The\s+(?:camera|scene|shot|video|opening|viewer|frame)|"
    r"Luxury|Elegant|Dramatic|Epic\s"
    r")",
    re.M,
)

# Leftover short metadata fragments after a label split.
_META_FRAG = re.compile(
    r"(?i)^(?:"
    r"(?:for|with|on|in|using|via)\s+(?:seedance|sd|bytedance|capcut|pollo|lart|higgsfield)(?:\s+\d+(?:\.\d+)?)?\s*"
    r"|Images\s*:.*?(?=\[)"
    r"|Video\s*:.*?(?=\[)"
    r")\s*",
    re.S,
)

# Inline structural/visual marker for _post_clean.
_INLINE_PROMPT_START = re.compile(
    r"(?i)(?:"
    r"\[(?:CINEMATIC|SETUP|STYLE|SHOT|SCENE|TECHNICAL|DURATION|CAMERA)"
    r"|\*\*\w"
    r"|\{"
    r"|SHOT\s*:"
    r"|Scene\s*\d"
    r"|\d{1,2}\s*[–—-]\s*\d{1,2}\s*s\b"
    r"|Ultra[- ]?\s*cinematic|Hyper[- ]?\s*realistic|Cinematic\b"
    r"|Photorealistic|Shot on|Generate\s+a|Create\s+a"
    r"|Handheld|Aerial|First[- ]person|POV\b|FPV\b"
    r"|Strictly\s+follow"
    r"|A\s+(?:towering|massive|tiny|young|old|lone|dark|bright|matte|sleek|luxury)"
    r"|The\s+(?:camera|scene|shot|video|opening|viewer|frame)"
    r")",
)


# ─── Commercial content stripping (INLINE — works anywhere) ─────────────────

def _build_commercial_line_re(handles: set[str]) -> re.Pattern[str]:
    """Build a regex that matches whole lines containing commercial @handles."""
    escaped = sorted((re.escape(h) for h in handles), key=len, reverse=True)
    handle_alt = "|".join(escaped)
    return re.compile(
        rf"(?mi)^[^\n]*@(?:{handle_alt})\b[^\n]*$"
    )


def _build_commercial_sentence_re(handles: set[str], brands: set[str]) -> re.Pattern[str]:
    """Match promotional sentences containing tool/brand names anywhere."""
    verbs = r"(?:made|created|generated|produced|built|rendered|crafted|powered|edited|designed|shot)"
    preps = r"(?:on|with|using|in|by|via|through|from)"
    escaped_handles = sorted((re.escape(h) for h in handles), key=len, reverse=True)
    escaped_brands = sorted((re.escape(b) for b in brands), key=len, reverse=True)
    name_alt = "|".join(escaped_handles + escaped_brands)
    return re.compile(
        rf"(?i)(?:"
        rf"{verbs}\s+{preps}\s+(?:@)?(?:{name_alt})"
        rf"|(?:try|check\s+out|download|get|use)\s+(?:@)?(?:{name_alt})"
        rf"|(?:tool|app|model|platform|engine)\s*[:：]?\s*(?:@)?(?:{name_alt})"
        rf")",
    )


def _build_commercial_inline_re(handles: set[str]) -> re.Pattern[str]:
    escaped = sorted((re.escape(h) for h in handles), key=len, reverse=True)
    handle_alt = "|".join(escaped)
    return re.compile(rf"(?i)@(?:{handle_alt})\b")


def _sentence_has_promo_hashtag(sentence: str) -> bool:
    for m in re.finditer(r"#([\w\u00c0-\u024f]+)", sentence):
        raw = m.group(1).lower()
        if raw in _PROMO_HASHTAG_EXACT:
            return True
        for stem in _PROMO_HASHTAG_PREFIX:
            if raw == stem or raw.startswith(stem):
                return True
    return False


def _strip_trailing_hashtag_block(text: str) -> str:
    """Remove trailing #hashtag runs and final lines that are only hashtags."""
    result = text
    while True:
        prev = result
        result = _TRAILING_HASHTAG_RUN.sub("", result)
        lines = result.split("\n")
        while lines:
            last_stripped = lines[-1].strip()
            if not last_stripped:
                lines.pop()
                continue
            if _LINE_ONLY_HASHTAGS.fullmatch(last_stripped):
                lines.pop()
                continue
            break
        result = "\n".join(lines)
        if result == prev:
            break
    return result


def _strip_promotional_units(
    text: str,
    handles: set[str],
    protected_lower: set[str],
) -> str:
    """Drop whole lines or sentences that exist only to promote tools / tags."""
    at_re = _build_commercial_inline_re(handles)
    out_lines: list[str] = []

    for raw_line in text.split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            out_lines.append("")
            continue
        low = stripped.lower()
        if any(p in low for p in protected_lower):
            out_lines.append(stripped)
            continue
        if _LINE_ONLY_HASHTAGS.fullmatch(stripped):
            continue

        parts = re.split(r"(?<=[.!?])\s+", stripped)
        if len(parts) <= 1:
            unit = stripped
            if at_re.search(unit) and len(unit.split()) <= 48:
                continue
            if _sentence_has_promo_hashtag(unit) and len(unit.split()) <= 44:
                continue
            out_lines.append(stripped)
            continue

        kept: list[str] = []
        for sent in parts:
            s = sent.strip()
            if not s:
                continue
            slow = s.lower()
            if any(p in slow for p in protected_lower):
                kept.append(sent)
                continue
            if at_re.search(s):
                continue
            if _sentence_has_promo_hashtag(s):
                continue
            kept.append(sent)
        out_lines.append(" ".join(kept) if kept else "")

    return "\n".join(out_lines)


def _strip_commercial(text: str) -> str:
    """Remove commercial content from anywhere in the text."""
    handles = _all_commercial_handles()
    brands = _BUILTIN_COMMERCIAL_BRANDS

    protected = {p.lower() for p in _all_protected_phrases()}

    # Phase 1: Remove full lines that are purely commercial (@handle promotion)
    line_re = _build_commercial_line_re(handles)
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue
        # Check if line is protected
        if any(p in stripped.lower() for p in protected):
            cleaned_lines.append(line)
            continue
        # Remove lines that are primarily commercial (short line with @handle)
        if line_re.match(stripped):
            words = stripped.split()
            # Only remove if the line is short (promotional) not a long prompt line
            # that happens to mention a tool
            if len(words) <= 40:
                continue
        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)

    # Phase 1b: drop promo-only sentences / short lines with tool @ or marketing #tags
    result = _strip_promotional_units(result, handles, protected)

    # Phase 2: Strip inline promotional sentence fragments
    sent_re = _build_commercial_sentence_re(handles, brands)
    # Remove the matched fragment and any surrounding fluff on the same "sentence"
    result = sent_re.sub("", result)

    # Phase 3: Apply learned strip_phrases
    for phrase in _all_strip_phrases():
        try:
            result = re.sub(re.escape(phrase), "", result, flags=re.IGNORECASE)
        except re.error:
            result = result.replace(phrase, "")

    # Clean up leftover whitespace
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r"[ \t]+", " ", result)
    return result.strip()


# ─── Chatter detection ──────────────────────────────────────────────────────

def _looks_prompt_like(text: str) -> bool:
    """Return True if *text* begins with prompt-like content, not chatter."""
    s = text[:120].strip()
    if not s:
        return False
    if _STRUCT_START.match(s):
        return True
    if _VISUAL_CUE.match(s):
        return True
    if s[0] in ('"', "'", '{', '['):
        return True
    low = s.lower()
    chatter = (
        "i ", "i'", "i\u2019", "it'", "it ", "my ", "we ", "we'",
        "just ", "this ", "here", "no ", "the seedance", "seedance",
        "bytedance", "check ", "wow", "from 1888", "in 1888",
        "she'", "he'", "they", "you ", "get ", "another ",
        "one --sref", "60-second cinematic",
    )
    return not any(low.startswith(c) for c in chatter)


# ─── Core trim pipeline ────────────────────────────────────────────────────

def trim_to_prompt_body(text: str) -> str:
    """Return only the copy-paste-ready prompt body from *text*."""
    if not text or not text.strip():
        return text or ""

    body = text.strip()
    body = _strip_tail(body)
    body = _strip_commercial(body)
    body = _strip_preamble(body)
    body = _strip_tail(body)
    body = _strip_commercial(body)
    return body.strip()


def _strip_preamble(text: str) -> str:
    # Gather ALL label match positions (end offsets).
    positions: list[int] = []
    for pat in _LABEL_RE:
        for m in pat.finditer(text):
            positions.append(m.end())

    # Try from the LATEST position backward.
    for end_pos in sorted(set(positions), reverse=True):
        candidate = text[end_pos:].strip()
        if len(candidate) >= 30 and _looks_prompt_like(candidate):
            return _post_clean(candidate)

    # Structural / visual cue fallback.
    im = _INLINE_PROMPT_START.search(text)
    if im and im.start() > 0:
        before = text[:im.start()].strip()
        candidate = text[im.start():].strip()
        if len(candidate) >= 30 and not _looks_prompt_like(before):
            return candidate

    return text


def _post_clean(text: str) -> str:
    """After label split, strip residual metadata then advance to nearest marker."""
    cleaned = _META_FRAG.sub("", text).strip()
    if len(cleaned) < 30:
        cleaned = text

    im = _INLINE_PROMPT_START.search(cleaned)
    if im and 0 < im.start() < 150:
        after = cleaned[im.start():].strip()
        if len(after) >= 30:
            return after

    return cleaned


def _strip_tail(text: str) -> str:
    result = text
    for pat in _TAIL_NOISE:
        result = pat.sub("", result)
    result = _strip_trailing_hashtag_block(result)
    return result.strip()
