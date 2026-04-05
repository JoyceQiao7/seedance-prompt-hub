"""Thresholds and $0-source search configuration."""

# X API v2 recent search queries (optional; often paid — safe to omit).
SEARCH_QUERIES: list[str] = [
    '("Seedance 2" OR Seedance2 OR "Seedance 2.0" OR SD2.0) -is:retweet lang:en',
    '("Seedance" prompt) -is:retweet lang:en',
    '(ByteDance Seedance OR "video model" Seedance) -is:retweet lang:en',
]

# Bluesky: app.bsky.feed.searchPosts — free with account + app password.
BLUESKY_SEARCH_QUERIES: list[str] = [
    "Seedance",
    "Seedance 2",
    "Seedance 2.0",
    "SD2 video",
    "ByteDance Seedance",
    "video generation prompt",
]

# Mastodon: public tag timelines (no token if instance allows).
MASTODON_INSTANCES: list[str] = [
    "https://mastodon.social",
    "https://hachyderm.io",
    "https://fosstodon.org",
    "https://mstdn.social",
]

MASTODON_TAGS: list[str] = [
    "seedance",
    "seedance2",
    "sd2",
    "seedance2prompt",
    "bytedance",
]

# Minimum heuristic quality (0–100) to keep a row without LLM override.
MIN_HEURISTIC_SCORE = 42

# Cap LLM-reviewed new items per run (cost control; optional OpenAI).
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
