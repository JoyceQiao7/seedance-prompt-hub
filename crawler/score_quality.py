"""Heuristic quality score 0–100 for a prompt string."""

from __future__ import annotations

import re


_SPAM = re.compile(
    r"(?i)(giveaway|airdrop|follow\s+me|dm\s+me|onlyfans|crypto|nft|telegram\s+link)"
)


def score_prompt(text: str) -> int:
    if not text:
        return 0
    if _SPAM.search(text):
        return 0

    score = 48
    n = len(text)
    words = len(text.split())

    # Length sweet spot for video prompts
    if 80 <= n <= 2200:
        score += 12
    elif 40 <= n < 80:
        score += 6
    elif n > 2200:
        score += 4

    if 12 <= words <= 220:
        score += 8

    lower = text.lower()
    structure_hits = sum(
        1
        for ch in (",", ";", "—", "-", ":", ".")
        if text.count(ch) >= 1
    )
    score += min(structure_hits * 3, 12)

    specificity = (
        "camera",
        "lens",
        "mm",
        "f/",
        "iso",
        "shutter",
        "fps",
        "dolly",
        "pan",
        "tilt",
        "tracking",
        "aerial",
        "close-up",
        "wide",
        "cinematic",
        "4k",
        "8k",
        "hdr",
        "film grain",
        "color grade",
    )
    score += min(18, 3 * sum(1 for t in specificity if t in lower))

    # Penalize hashtag / handle noise
    score -= min(20, text.count("#") * 3)
    score -= min(16, text.count("@") * 4)

    # Boost if model is explicitly referenced (dataset signal)
    if "seedance" in lower or "sd2" in lower.replace(".", ""):
        score += 6

    return max(0, min(100, score))
