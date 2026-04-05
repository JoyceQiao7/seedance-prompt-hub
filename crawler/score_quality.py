"""Heuristic quality score 0–100 for a prompt string.

Calibrated so that detailed, copy-paste-ready video prompts reach 90+,
while commentary / news-style posts about AI video stay below."""

from __future__ import annotations

import re


_SPAM = re.compile(
    r"(?i)(giveaway|airdrop|follow\s+me|dm\s+me|onlyfans|crypto|nft|telegram\s+link)"
)


def looks_spammy(text: str) -> bool:
    return bool(text and _SPAM.search(text))


_PROMPT_CUE = re.compile(
    r"(?i)(prompt\s*[:：]|full\s*prompt|camera\s*[:：]|scene\s*\d|"
    r"\[cinematic|lens\s*[:：]|shot\s*[:：]|lighting\s*[:：]|"
    r"close[\s-]up|wide[\s-]shot|medium[\s-]shot|tracking\s*shot|"
    r"dolly|crane|steadicam|handheld|aerial|drone\s*shot|"
    r"35mm|anamorphic|film\s*grain|color\s*grad|"
    r"f/\d|iso\s*\d|\d+mm|shutter|bokeh|depth\s*of\s*field|"
    r"fps|aspect\s*ratio|\d+:\d+\s|4k|8k|hdr|"
    r"ray\s*tracing|unreal\s*engine|hyper[\s-]?detail)"
)

_COMMENTARY = re.compile(
    r"(?i)(just\s*dropped|just\s*launched|here'?s?\s+how|game[\s-]?changer|"
    r"try\s+it\s+here|check\s+out|sign\s+up|next\s+level|"
    r"about\s+to\s+change|insane\s+too|let'?s?\s+go|"
    r"the\s+future\s+of|this\s+is\s+huge|key\s+features|"
    r"launched\s+today|now\s+live|integration\s+is|"
    r"leveled\s+up|doing\s+wonders)"
)


def score_prompt(text: str) -> int:
    if not text:
        return 0
    if looks_spammy(text):
        return 0

    score = 40
    n = len(text)
    words = len(text.split())
    lower = text.lower()

    # --- Length ---
    if 120 <= n <= 2200:
        score += 15
    elif 80 <= n < 120:
        score += 8
    elif 40 <= n < 80:
        score += 4
    elif n > 2200:
        score += 6

    if 15 <= words <= 250:
        score += 6

    # --- Structural punctuation (prompts are descriptive, heavily punctuated) ---
    struct = sum(1 for ch in (",", ";", ":", ".", "—", "-") if text.count(ch) >= 2)
    score += min(struct * 3, 12)

    # --- Prompt-specific vocabulary (camera, lens, grade, etc.) ---
    spec_terms = (
        "camera", "lens", "mm", "f/", "iso", "shutter", "fps",
        "dolly", "pan", "tilt", "tracking", "aerial", "close-up",
        "wide shot", "medium shot", "cinematic", "4k", "8k", "hdr",
        "film grain", "color grade", "anamorphic", "35mm",
        "ray tracing", "unreal engine", "bokeh", "depth of field",
        "aspect ratio", "slow zoom", "crane", "steadicam", "handheld",
        "golden hour", "rim light", "backlit", "volumetric",
        "scene 1", "scene 2", "act 1", "act 2",
    )
    spec_hits = sum(1 for t in spec_terms if t in lower)
    score += min(24, spec_hits * 4)

    # --- Looks like an actual usable prompt (big bonus) ---
    cue_hits = len(_PROMPT_CUE.findall(text))
    if cue_hits >= 3:
        score += 16
    elif cue_hits >= 1:
        score += 8

    # --- Rich visual / descriptive language (actual prompt-like) ---
    visual = (
        "realistic", "photorealistic", "detailed", "vivid",
        "dramatic", "moody", "warm", "cold", "dark", "bright",
        "sharp", "soft", "blurry", "shallow", "deep",
        "texture", "reflection", "shadow", "silhouette",
        "saturated", "desaturated", "muted", "vibrant",
        "smoke", "fog", "haze", "dust", "rain", "snow",
        "skin", "hair", "eyes", "expression", "gaze",
        "fabric", "glass", "metal", "water", "fire",
    )
    vis_hits = sum(1 for v in visual if v in lower)
    score += min(12, vis_hits * 3)

    # --- Commentary / news style (penalty) ---
    commentary_hits = len(_COMMENTARY.findall(text))
    score -= min(20, commentary_hits * 8)

    # --- Noise penalties ---
    score -= min(18, text.count("#") * 3)
    score -= min(14, text.count("@") * 4)
    url_count = len(re.findall(r"https?://\S+", text))
    score -= min(16, url_count * 6)

    # --- Model reference (mild dataset signal) ---
    if "seedance" in lower or "sd2" in lower.replace(".", ""):
        score += 4

    return max(0, min(100, score))
