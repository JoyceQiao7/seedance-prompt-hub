"""Crawler thresholds and X search queries (unofficial scrape)."""

X_SCRAPE_QUERIES: list[str] = [
    "Seedance 2.0 prompt",
    "Seedance 2 prompt",
    "Seedance2 prompt",
    "SD2.0 prompt",
    "Seedance 2.0",
    "Seedance 2",
    '"Seedance" prompt',
    "Seedance text to video",
    "Seedance cinematic",
    "Seedance AI video",
    "ByteDance Seedance prompt",
]

MIN_HEURISTIC_SCORE = 42
SCREEN_MIN_SCORE = 48
PUBLIC_MIN_QUALITY = 90

CATEGORIES: tuple[str, ...] = (
    "cinematic",
    "commercial",
    "music-video",
    "social-content",
    "character",
    "nature-scenic",
    "vfx",
    "other",
)
