"""Filter scraped posts to AI video / generative-video creator niche."""

from __future__ import annotations

import re

# Broad but still on-topic for this hub (tune in config if needed).
_MARKERS: tuple[str, ...] = (
    "seedance",
    "bytedance",
    "sd2",
    "sora",
    "runway",
    "gen-3",
    "gen3",
    "kling",
    "pika",
    "luma",
    "dream machine",
    "veo",
    "wan ",
    "wan2",
    "minimax",
    "hailuo",
    "haiper",
    "pixverse",
    "text to video",
    "text-to-video",
    "ai video",
    "video model",
    "video prompt",
    "cinematic prompt",
    "t2v",
    "i2v",
)


def is_ai_video_creator_content(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    if "seedance" in lower or "bytedance" in lower:
        return True
    if "sd2.0" in lower or "sd 2.0" in lower:
        return True
    if re.search(r"\bsd2\b", lower):
        return True
    return any(m in lower for m in _MARKERS)


# Back-compat name used in tests / imports
is_seedance_related = is_ai_video_creator_content
