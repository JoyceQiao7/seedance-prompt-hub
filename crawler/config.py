"""Search and quality thresholds for the X crawler."""

# X API v2 recent search queries (OR-clauses must stay within API limits).
SEARCH_QUERIES: list[str] = [
    '("Seedance 2" OR Seedance2 OR "Seedance 2.0" OR SD2.0) -is:retweet lang:en',
    '("Seedance" prompt) -is:retweet lang:en',
    '(ByteDance Seedance OR "video model" Seedance) -is:retweet lang:en',
]

# Minimum heuristic quality (0–100) to keep a row without LLM override.
MIN_HEURISTIC_SCORE = 42

# Cap LLM-reviewed new items per run (cost control).
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
