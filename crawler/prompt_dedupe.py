"""Skip near-duplicate prompt bodies across the store and within a crawl run."""

from __future__ import annotations

import os
import re
import unicodedata
from difflib import SequenceMatcher

_WS = re.compile(r"\s+")


def normalize_prompt_for_dedupe(text: str) -> str:
    """Lowercase, Unicode-normalize, collapse whitespace for comparison."""
    s = unicodedata.normalize("NFKC", text or "")
    s = _WS.sub(" ", s.strip().lower())
    return s


def _similar_enough(a: str, b: str, threshold: float) -> bool:
    if not a or not b:
        return False
    la, lb = len(a), len(b)
    shorter, longer = (a, b) if la <= lb else (b, a)
    if len(shorter) >= 50 and shorter in longer:
        return True
    mx = max(la, lb)
    if mx < 80:
        return False
    if abs(la - lb) / mx > 0.22:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


class PromptDeduper:
    """Exact + fuzzy duplicate detection using existing prompts and in-run additions."""

    def __init__(
        self,
        existing_prompts: list[dict],
        *,
        similarity_threshold: float = 0.93,
        fuzzy: bool = True,
        min_chars: int = 24,
    ) -> None:
        self._similarity = similarity_threshold
        self._fuzzy = fuzzy
        self._min = min_chars
        self._exact: set[str] = set()
        self._corpus: list[str] = []
        for p in existing_prompts:
            if not isinstance(p, dict):
                continue
            for key in ("text", "display_text"):
                t = p.get(key)
                if isinstance(t, str) and t.strip():
                    self._index_text(t)

    @classmethod
    def from_env(cls, existing_prompts: list[dict]) -> PromptDeduper:
        raw = (os.environ.get("X_DEDUPE_SIMILARITY") or "").strip()
        threshold = float(raw) if raw else 0.93
        fuzzy = os.environ.get("X_DEDUPE_FUZZY", "1").lower() not in ("0", "false", "no")
        min_c = int(os.environ.get("X_DEDUPE_MIN_CHARS") or "24")
        return cls(existing_prompts, similarity_threshold=threshold, fuzzy=fuzzy, min_chars=min_c)

    def _index_text(self, text: str) -> None:
        n = normalize_prompt_for_dedupe(text)
        if len(n) < self._min:
            return
        self._exact.add(n)
        self._corpus.append(n)

    def is_duplicate(self, prompt_text: str) -> bool:
        n = normalize_prompt_for_dedupe(prompt_text)
        if len(n) < self._min:
            return False
        if n in self._exact:
            return True
        if not self._fuzzy:
            return False
        for other in self._corpus:
            if _similar_enough(n, other, self._similarity):
                return True
        return False

    def remember(self, prompt_text: str) -> None:
        """Record a prompt accepted this run so later items in the same batch dedupe against it."""
        self._index_text(prompt_text)
