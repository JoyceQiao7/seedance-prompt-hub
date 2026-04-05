"""Crawler thresholds and X search queries (unofficial scrape)."""

X_SCRAPE_QUERIES: list[str] = [
    "Seedance AI video",
    "Seedance 2 prompt",
    "ByteDance Seedance",
    "Seedance text to video",
    "AI video prompt cinematic",
    "Runway Gen-3 video prompt",
    "Kling AI video prompt",
    "Sora video prompt",
    "Pika Labs video prompt",
    "Luma Dream Machine prompt",
    "Google Veo video",
    "Minimax video AI",
    "Wan video AI",
    "PixVerse AI video",
    "text to video prompt",
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
