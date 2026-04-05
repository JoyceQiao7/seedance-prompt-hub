"""Only keep posts that are specifically about Seedance / SD2."""

from __future__ import annotations

import re


def is_seedance_content(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    if "seedance" in lower:
        return True
    if "sd2.0" in lower or "sd 2.0" in lower:
        return True
    if re.search(r"\bsd2\b", lower):
        return True
    return False


# Keep the old name as alias so imports don't break
is_ai_video_creator_content = is_seedance_content
