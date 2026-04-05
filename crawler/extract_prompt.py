"""Pull a usable Seedance-style prompt string out of tweet text."""

from __future__ import annotations

import re


def extract_prompt(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None

    # Explicit labels often used on X
    for label in (
        r"(?i)prompt\s*[:：]\s*",
        r"(?i)full\s*prompt\s*[:：]\s*",
        r"(?i)sd2\s*prompt\s*[:：]\s*",
        r"(?i)seedance\s*prompt\s*[:：]\s*",
    ):
        m = re.search(label + r"(.+)", text, re.DOTALL)
        if m:
            candidate = _clean_block(m.group(1))
            if _is_substantial(candidate):
                return candidate

    # Quoted block
    m = re.search(r'["""](.+?)["""]', text, re.DOTALL)
    if m:
        candidate = _clean_block(m.group(1))
        if _is_substantial(candidate):
            return candidate

    # Code-fence style
    m = re.search(r"```(?:\w*\n)?(.+?)```", text, re.DOTALL)
    if m:
        candidate = _clean_block(m.group(1))
        if _is_substantial(candidate):
            return candidate

    # Whole tweet if it reads like a dense prompt
    stripped = re.sub(r"https?://\S+", "", text)
    stripped = _clean_block(stripped)
    if _is_substantial(stripped) and _looks_like_prompt(stripped):
        return stripped

    return None


def _clean_block(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _is_substantial(s: str) -> bool:
    return len(s) >= 24


def _looks_like_prompt(s: str) -> bool:
    lower = s.lower()
    if len(s) < 60:
        return False
    # Heuristic: descriptive + not mostly hashtags/handles
    wordish = re.findall(r"[a-zA-Z]{3,}", s)
    if len(wordish) < 8:
        return False
    hash_ratio = s.count("#") / max(len(s), 1)
    at_ratio = s.count("@") / max(len(s), 1)
    if hash_ratio > 0.08 or at_ratio > 0.06:
        return False
    cue = (
        "camera",
        "shot",
        "dolly",
        "pan",
        "zoom",
        "tracking",
        "cinematic",
        "4k",
        "slow motion",
        "aerial",
        "close-up",
        "wide",
        "seedance",
        "lighting",
        "golden hour",
        "style",
        "film",
        "scene",
    )
    return any(c in lower for c in cue)
