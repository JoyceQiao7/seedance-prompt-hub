"""Strip social-media preamble and trailing noise, keeping only the prompt body."""

from __future__ import annotations

import re

# ── Trailing noise (stripped FIRST so label-matching doesn't hit them) ──────
_TAIL_NOISE: list[re.Pattern[str]] = [
    re.compile(r"(?i)\.{3,}\s*Find the rest.*$", re.S),
    re.compile(r"(?i)\bFind the rest of.*$", re.S),
    re.compile(r"(?i)\bFind the rest\b.*$", re.S),
    re.compile(r"(?i)\bFollow (?:me|us|for)\b.*$", re.S),
    re.compile(r"(?i)\bLink in bio\b.*$", re.S),
    re.compile(r"(?i)\bSign up\b.*$", re.S),
    re.compile(r"(?i)\bGr[ea]ding\s*[:：]?\s*@\w+.*$", re.S),
    re.compile(r"(?:(?:\s*#\w+){3,})\s*$"),
    re.compile(r"(?:\s*@\w+){3,}\s*$"),
]

# ── Prompt-label patterns ───────────────────────────────────────────────────
# Order doesn't matter — we gather all matches and pick the best.
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

# Leftover short metadata fragments after a label split (case-insensitive).
_META_FRAG = re.compile(
    r"(?i)^(?:"
    r"(?:for|with|on|in|using|via)\s+(?:seedance|sd|bytedance|capcut|pollo|lart|higgsfield)(?:\s+\d+(?:\.\d+)?)?\s*"
    r"|Images\s*:.*?(?=\[)"
    r"|Video\s*:.*?(?=\[)"
    r")\s*",
    re.S,
)

# Inline structural/visual marker (no line-start anchor) for _post_clean.
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
        "i ", "i'", "i'", "it'", "it ", "my ", "we ", "we'",
        "just ", "this ", "here", "no ", "the seedance", "seedance",
        "bytedance", "check ", "wow", "from 1888", "in 1888",
        "she'", "he'", "they", "you ", "get ", "another ",
        "one --sref", "60-second cinematic",
    )
    return not any(low.startswith(c) for c in chatter)


def trim_to_prompt_body(text: str) -> str:
    """Return only the copy-paste-ready prompt body from *text*."""
    if not text or not text.strip():
        return text or ""

    body = text.strip()
    body = _strip_tail(body)
    body = _strip_preamble(body)
    body = _strip_tail(body)
    return body.strip()


def _strip_preamble(text: str) -> str:
    # Gather ALL label match positions (end offsets).
    positions: list[int] = []
    for pat in _LABEL_RE:
        for m in pat.finditer(text):
            positions.append(m.end())

    # Try from the LATEST position backward — the last real label is usually
    # the actual divider (handles "PromptShare ... PROMPT ..." cascades).
    for end_pos in sorted(set(positions), reverse=True):
        candidate = text[end_pos:].strip()
        if len(candidate) >= 30 and _looks_prompt_like(candidate):
            return _post_clean(candidate)

    # Structural / visual cue fallback (works mid-line).
    # Only trigger if there's clear non-prompt preamble before the cue.
    im = _INLINE_PROMPT_START.search(text)
    if im and im.start() > 0:
        before = text[:im.start()].strip()
        candidate = text[im.start():].strip()
        if len(candidate) >= 30 and not _looks_prompt_like(before):
            return candidate

    return text


def _post_clean(text: str) -> str:
    """After label split, strip residual metadata fragments then advance to
    the nearest structural/visual marker if one appears soon."""
    cleaned = _META_FRAG.sub("", text).strip()
    if len(cleaned) < 30:
        cleaned = text

    # If an inline prompt-start marker appears in the first 150 chars and
    # isn't at position 0, advance to it.
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
    return result.strip()
