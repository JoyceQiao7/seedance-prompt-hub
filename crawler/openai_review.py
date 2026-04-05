"""Optional LLM pass to normalize prompt text and refine score/category."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from crawler.config import CATEGORIES


def review_prompt(tweet_text: str, draft_prompt: str) -> dict[str, Any] | None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None

    system = (
        "You curate Seedance 2.0 (ByteDance video) generation prompts from X posts. "
        "Return strict JSON only with keys: "
        'clean_prompt (string), category (one of: '
        + ", ".join(CATEGORIES)
        + "), quality (integer 1-10), keep (boolean). "
        "keep=false if there is no real generative prompt. "
        "clean_prompt should be the best standalone English prompt, no hashtags or handles."
    )
    user = json.dumps(
        {"tweet": tweet_text, "extracted_draft": draft_prompt},
        ensure_ascii=False,
    )

    body = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0].strip()
        parsed = json.loads(content)

    cat = parsed.get("category")
    if cat not in CATEGORIES:
        cat = "other"
    q = int(parsed.get("quality") or 0)
    q = max(1, min(10, q))
    return {
        "clean_prompt": (parsed.get("clean_prompt") or "").strip(),
        "category": cat,
        "quality_10": q,
        "keep": bool(parsed.get("keep", True)),
    }
