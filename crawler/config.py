"""Crawler thresholds and X search queries (unofficial scrape)."""

# Human-readable X search strings (Latest tab). Keep modest count to reduce blocks.
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

# Minimum heuristic quality (0–100) to keep a row without LLM override.
MIN_HEURISTIC_SCORE = 42

# Cap LLM-reviewed new items per run (optional OpenAI; costs money).
MAX_LLM_REVIEWS_PER_RUN = 40

CATEGORIES: tuple[str, ...] = (
    "motion",
    "camera",
    "character",
    "scene",
    "style",
    "lighting",
    "audio",
    "other",
)
