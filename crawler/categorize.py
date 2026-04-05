"""Assign a coarse category from prompt text."""

from __future__ import annotations

from crawler.config import CATEGORIES


_KEYWORDS: dict[str, tuple[str, ...]] = {
    "motion": (
        "slow motion",
        "fast motion",
        "running",
        "walking",
        "dancing",
        "jumping",
        "floating",
        "spinning",
        "explosion",
        "particles",
        "wind",
        "water splash",
        "motion blur",
    ),
    "camera": (
        "dolly",
        "pan",
        "tilt",
        "tracking shot",
        "handheld",
        "steadicam",
        "crane",
        "aerial",
        "drone",
        "close-up",
        "wide shot",
        "medium shot",
        "overhead",
        "pov",
        "macro",
        "rack focus",
    ),
    "character": (
        "woman",
        "man",
        "child",
        "elder",
        "portrait",
        "face",
        "expression",
        "outfit",
        "costume",
        "cyborg",
        "robot",
        "warrior",
        "model",
    ),
    "scene": (
        "forest",
        "city",
        "street",
        "beach",
        "mountain",
        "desert",
        "interior",
        "kitchen",
        "office",
        "studio",
        "space",
        "underwater",
        "rain",
        "snow",
        "sunset",
        "night",
    ),
    "style": (
        "anime",
        "pixar",
        "3d render",
        "claymation",
        "stop motion",
        "watercolor",
        "oil painting",
        "noir",
        "vaporwave",
        "retro",
        "futuristic",
        "documentary",
        "commercial",
    ),
    "lighting": (
        "lighting",
        "rim light",
        "backlit",
        "neon",
        "volumetric",
        "soft light",
        "hard light",
        "golden hour",
        "blue hour",
        "chiaroscuro",
        "studio lighting",
    ),
    "audio": (
        "sound",
        "music",
        "ambient",
        "dialogue",
        "voice",
        "sfx",
        "score",
    ),
}


def categorize(text: str) -> str:
    lower = text.lower()
    best = "other"
    best_hits = 0
    for cat in CATEGORIES:
        if cat == "other":
            continue
        hits = sum(1 for kw in _KEYWORDS.get(cat, ()) if kw in lower)
        if hits > best_hits:
            best = cat
            best_hits = hits
    return best
