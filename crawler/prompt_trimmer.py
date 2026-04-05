"""Strip social-media preamble, commercial content, and trailing noise.

The trimmer operates in three layers:
1. Built-in rules  — hardcoded patterns compiled at import time.
2. Learned rules   — loaded from data/trim_rules.json (written by admin feedback).
3. Inline cleaning — removes commercial @handles and brand mentions anywhere.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
_RULES_PATH = _ROOT / "data" / "trim_rules.json"

# ── Built-in AI-tool handles (lowercased, without @) ────────────────────────
# Comprehensive seed list — extended automatically by admin feedback.
_BUILTIN_COMMERCIAL_HANDLES: set[str] = {
    "lumalabsai", "lumaai", "runwayml", "runwayapp",
    "pixaborai", "pixverseai", "pixverse_ai", "pixverse",
    "kaborai", "kaboraai", "klingai", "kling_ai",
    "hailuoai", "hailuoai_official", "miniabormax", "minimax_ai",
    "martiniai", "martiniart_", "martiniai_",
    "paborika_app", "pikapikapika", "pika_labs",
    "genmoai", "genmo_ai",
    "viduofficial", "vidu_ai",
    "morphstudioai", "morph_ai",
    "domoai", "domo_ai",
    "leonardoai", "leonardo_ai",
    "midaborjourney", "midjourney",
    "openai", "openai_",
    "staaborility_ai", "stabilityai",
    "adobe", "adobefirefly",
    "canva", "capcut", "capcutapp",
    "invaborideoai", "invideo_ai",
    "synthaboresia", "synthesia_io",
    "heygen_official", "heygenofficial",
    "d_id_", "d_id_official",
    "topaborazlabs", "topazorlabs",
    "magnific_ai", "magnaborific",
    "ideaborogram", "ideogram_ai",
    "fluxai", "flux_ai",
    "seedance", "seedanceai",
    "bytedance", "bytedanceai",
    "polloai", "pollo_ai",
    "higgsfield", "higgsfield_ai",
    "lart_ai", "lartai",
    "haiper_ai", "haiperofficial",
    "dreamina_ai", "dreamina",
    "noisee_ai", "noiseeai",
    "suno_ai_", "sunomusic",
    "udiomusic",
    "elevenaborlabs", "elevenlabs",
}

# ── Built-in commercial brand names (for inline sentence matching) ───────────
_BUILTIN_COMMERCIAL_BRANDS: set[str] = {
    "luma", "luma labs", "runway", "runway ml",
    "pixverse", "kling", "kling ai",
    "hailuo", "hailuo ai", "minimax",
    "martini art", "martiniai",
    "pika", "pika labs",
    "genmo", "vidu",
    "morph studio", "domo ai",
    "leonardo ai", "midjourney",
    "stability ai", "stable diffusion",
    "adobe firefly", "canva", "capcut",
    "invideo", "synthesia", "heygen", "d-id",
    "topaz labs", "magnific",
    "ideogram", "flux",
    "seedance", "bytedance",
    "pollo ai", "higgsfield",
    "lart ai", "haiper",
    "dreamina", "noisee",
    "suno", "udio", "eleven labs",
}

# ── Learned rules cache ─────────────────────────────────────────────────────
_learned: dict[str, Any] | None = None


def _load_learned() -> dict[str, Any]:
    """Load learned rules from disk (cached after first call)."""
    global _learned
    if _learned is not None:
        return _learned
    if _RULES_PATH.is_file():
        try:
            _learned = json.loads(_RULES_PATH.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            _learned = {}
    else:
        _learned = {}
    return _learned


def reload_learned() -> None:
    """Force-reload learned rules (call after admin updates them)."""
    global _learned
    _learned = None
    _load_learned()


def _all_commercial_handles() -> set[str]:
    rules = _load_learned()
    extra = {h.lower().lstrip("@") for h in rules.get("commercial_handles", [])}
    return _BUILTIN_COMMERCIAL_HANDLES | extra


def _all_strip_phrases() -> list[str]:
    rules = _load_learned()
    return list(rules.get("strip_phrases", []))


def _all_protected_phrases() -> list[str]:
    rules = _load_learned()
    return list(rules.get("protected_phrases", []))


# ── Trailing noise (stripped FIRST so label-matching doesn't hit them) ───────
_TAIL_NOISE: list[re.Pattern[str]] = [
    re.compile(r"(?i)\.{3,}\s*Find the rest.*$", re.S),
    re.compile(r"(?i)\bFind the rest of.*$", re.S),
    re.compile(r"(?i)\bFind the rest\b.*$", re.S),
    re.compile(r"(?i)\bFollow (?:me|us|for)\b.*$", re.S),
    re.compile(r"(?i)\bLink in bio\b.*$", re.S),
    re.compile(r"(?i)\bSign up\b.*$", re.S),
    re.compile(r"(?i)\bGr[ea]ding\s*[:：]?\s*@\w+.*$", re.S),
    re.compile(r"(?i)\s*[—–-]\s*(?:made\s+)?(?:on|with|by|via)?\s*@\w+\s*$"),
    re.compile(r"(?:(?:\s*#\w+){3,})\s*$"),
    re.compile(r"(?:\s*@\w+){3,}\s*$"),
]

# ── Prompt-label patterns ───────────────────────────────────────────────────
_LABEL_RE: list[re.Pattern[str]] = [
    re.compile(r"(?i)\b(?:full\s+)?prompt\s*[:：]\s*"),
    re.compile(r"\bPROMPT\s+"),
    re.compile(r"(?i)\bPrompt\s+(?:share|sharing)\s*[:：]?\s*"),
    re.compile(r"(?i)\bPromptShare\s*[:：]?\s+"),
    re.compile(r"(?i)\btext[- ]to[- ]video\s+prompt\s*[:：]?\s*"),
    re.compile(r"(?i)\b(?:seedance|sd)\s*2\.?0?\s+prompt\s*[:：]?\s*"),
    re.compile(r"(?i)プロンプト\s*[:：]?\s*"),
    re.compile(r"(?i)\bPrompt\s+(?=[A-Z\[\{\"*])"),
]

# Structural markers that signal the prompt body start.
_STRUCT_START = re.compile(
    r"(?m)^(?:"
    r"\[(?:CINEMATIC|SETUP|STYLE|SHOT|SCENE|TECHNICAL|DURATION|CAMERA|IMAGE)"
    r"|\*\*\w"
    r"|\{"
    r"|SHOT\s*:"
    r"|Scene\s*\d"
    r"|\d{1,2}\s*[–—-]\s*\d{1,2}\s*s\b"
    r")",
    re.I,
)

# Strong visual/cinematic sentence openers.
_VISUAL_CUE = re.compile(
    r"(?i)(?:^|\n)\s*"
    r"(?:"
    r"Ultra[- ]?\s*cinematic|Hyper[- ]?\s*realistic|Cinematic|Photorealistic|"
    r"Shot on|Generate\s+a|Create\s+a|"
    r"Handheld|Aerial|First[- ]person|POV|FPV|"
    r"Macro|Wide[- ]?angle|Close[- ]up|Medium[- ](?:shot|close)|Low[- ]angle|"
    r"Opening\s+frame|Establishing\s+shot|"
    r"Strictly\s+follow|"
    r"A\s+(?:towering|massive|tiny|young|old|lone|dark|bright|matte|sleek|luxury)|"
    r"The\s+(?:camera|scene|shot|video|opening|viewer|frame)|"
    r"Luxury|Elegant|Dramatic|Epic\s"
    r")",
    re.M,
)

# Leftover short metadata fragments after a label split.
_META_FRAG = re.compile(
    r"(?i)^(?:"
    r"(?:for|with|on|in|using|via)\s+(?:seedance|sd|bytedance|capcut|pollo|lart|higgsfield)(?:\s+\d+(?:\.\d+)?)?\s*"
    r"|Images\s*:.*?(?=\[)"
    r"|Video\s*:.*?(?=\[)"
    r")\s*",
    re.S,
)

# Inline structural/visual marker for _post_clean.
_INLINE_PROMPT_START = re.compile(
    r"(?i)(?:"
    r"\[(?:CINEMATIC|SETUP|STYLE|SHOT|SCENE|TECHNICAL|DURATION|CAMERA)"
    r"|\*\*\w"
    r"|\{"
    r"|SHOT\s*:"
    r"|Scene\s*\d"
    r"|\d{1,2}\s*[–—-]\s*\d{1,2}\s*s\b"
    r"|Ultra[- ]?\s*cinematic|Hyper[- ]?\s*realistic|Cinematic\b"
    r"|Photorealistic|Shot on|Generate\s+a|Create\s+a"
    r"|Handheld|Aerial|First[- ]person|POV\b|FPV\b"
    r"|Strictly\s+follow"
    r"|A\s+(?:towering|massive|tiny|young|old|lone|dark|bright|matte|sleek|luxury)"
    r"|The\s+(?:camera|scene|shot|video|opening|viewer|frame)"
    r")",
)


# ─── Commercial content stripping (INLINE — works anywhere) ─────────────────

def _build_commercial_line_re(handles: set[str]) -> re.Pattern[str]:
    """Build a regex that matches whole lines containing commercial @handles."""
    escaped = sorted((re.escape(h) for h in handles), key=len, reverse=True)
    handle_alt = "|".join(escaped)
    return re.compile(
        rf"(?mi)^[^\n]*@(?:{handle_alt})\b[^\n]*$"
    )


def _build_commercial_sentence_re(handles: set[str], brands: set[str]) -> re.Pattern[str]:
    """Match promotional sentences containing tool/brand names anywhere."""
    verbs = r"(?:made|created|generated|produced|built|rendered|crafted|powered|edited|designed|shot)"
    preps = r"(?:on|with|using|in|by|via|through|from)"
    escaped_handles = sorted((re.escape(h) for h in handles), key=len, reverse=True)
    escaped_brands = sorted((re.escape(b) for b in brands), key=len, reverse=True)
    name_alt = "|".join(escaped_handles + escaped_brands)
    return re.compile(
        rf"(?i)(?:"
        rf"{verbs}\s+{preps}\s+(?:@)?(?:{name_alt})"
        rf"|(?:try|check\s+out|download|get|use)\s+(?:@)?(?:{name_alt})"
        rf"|(?:tool|app|model|platform|engine)\s*[:：]?\s*(?:@)?(?:{name_alt})"
        rf")",
    )


def _strip_commercial(text: str) -> str:
    """Remove commercial content from anywhere in the text."""
    handles = _all_commercial_handles()
    brands = _BUILTIN_COMMERCIAL_BRANDS

    protected = {p.lower() for p in _all_protected_phrases()}

    # Phase 1: Remove full lines that are purely commercial (@handle promotion)
    line_re = _build_commercial_line_re(handles)
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue
        # Check if line is protected
        if any(p in stripped.lower() for p in protected):
            cleaned_lines.append(line)
            continue
        # Remove lines that are primarily commercial (short line with @handle)
        if line_re.match(stripped):
            words = stripped.split()
            # Only remove if the line is short (promotional) not a long prompt line
            # that happens to mention a tool
            if len(words) <= 20:
                continue
        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)

    # Phase 2: Strip inline promotional sentence fragments
    sent_re = _build_commercial_sentence_re(handles, brands)
    # Remove the matched fragment and any surrounding fluff on the same "sentence"
    result = sent_re.sub("", result)

    # Phase 3: Apply learned strip_phrases
    for phrase in _all_strip_phrases():
        try:
            result = re.sub(re.escape(phrase), "", result, flags=re.IGNORECASE)
        except re.error:
            result = result.replace(phrase, "")

    # Clean up leftover whitespace
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r"[ \t]+", " ", result)
    return result.strip()


# ─── Chatter detection ──────────────────────────────────────────────────────

def _looks_prompt_like(text: str) -> bool:
    """Return True if *text* begins with prompt-like content, not chatter."""
    s = text[:120].strip()
    if not s:
        return False
    if _STRUCT_START.match(s):
        return True
    if _VISUAL_CUE.match(s):
        return True
    if s[0] in ('"', "'", '{', '['):
        return True
    low = s.lower()
    chatter = (
        "i ", "i'", "i\u2019", "it'", "it ", "my ", "we ", "we'",
        "just ", "this ", "here", "no ", "the seedance", "seedance",
        "bytedance", "check ", "wow", "from 1888", "in 1888",
        "she'", "he'", "they", "you ", "get ", "another ",
        "one --sref", "60-second cinematic",
    )
    return not any(low.startswith(c) for c in chatter)


# ─── Core trim pipeline ────────────────────────────────────────────────────

def trim_to_prompt_body(text: str) -> str:
    """Return only the copy-paste-ready prompt body from *text*."""
    if not text or not text.strip():
        return text or ""

    body = text.strip()
    body = _strip_tail(body)
    body = _strip_commercial(body)
    body = _strip_preamble(body)
    body = _strip_tail(body)
    body = _strip_commercial(body)
    return body.strip()


def _strip_preamble(text: str) -> str:
    # Gather ALL label match positions (end offsets).
    positions: list[int] = []
    for pat in _LABEL_RE:
        for m in pat.finditer(text):
            positions.append(m.end())

    # Try from the LATEST position backward.
    for end_pos in sorted(set(positions), reverse=True):
        candidate = text[end_pos:].strip()
        if len(candidate) >= 30 and _looks_prompt_like(candidate):
            return _post_clean(candidate)

    # Structural / visual cue fallback.
    im = _INLINE_PROMPT_START.search(text)
    if im and im.start() > 0:
        before = text[:im.start()].strip()
        candidate = text[im.start():].strip()
        if len(candidate) >= 30 and not _looks_prompt_like(before):
            return candidate

    return text


def _post_clean(text: str) -> str:
    """After label split, strip residual metadata then advance to nearest marker."""
    cleaned = _META_FRAG.sub("", text).strip()
    if len(cleaned) < 30:
        cleaned = text

    im = _INLINE_PROMPT_START.search(cleaned)
    if im and 0 < im.start() < 150:
        after = cleaned[im.start():].strip()
        if len(after) >= 30:
            return after

    return cleaned


def _strip_tail(text: str) -> str:
    result = text
    for pat in _TAIL_NOISE:
        result = pat.sub("", result)
    return result.strip()
