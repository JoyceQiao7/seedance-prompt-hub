"""Keep posts that plausibly discuss Seedance / SD2.x / ByteDance video model prompts."""

from __future__ import annotations

import re


def is_seedance_related(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    if "seedance" in lower or "bytedance" in lower:
        return True
    if "sd2.0" in lower or "sd 2.0" in lower:
        return True
    if re.search(r"\bsd2\b", lower):
        return True
    return False
