"""Local admin server: edits ``data/prompts.json`` (canonical store, same as on GitHub).

From the repository root::

    python admin/server.py

Open: http://127.0.0.1:8090 (override with ``ADMIN_PORT``).

On save:
1. Writes the full store to ``data/prompts.json`` (``published`` per row; optional ``admin_feedback``)
2. Learns trim / screen rules under ``data/``
3. Copies ``data/prompts.json`` to ``web/public/prompts.json`` when that folder exists (local preview)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_DIR = Path(__file__).resolve().parent
RULES_PATH = ROOT / "data" / "trim_rules.json"
PORT = int(os.environ.get("ADMIN_PORT", "8090"))

sys.path.insert(0, str(ROOT))
from crawler.merge_store import prompt_store_path, save_store  # noqa: E402
from crawler.prompt_trimmer import reload_learned, trim_to_prompt_body  # noqa: E402
from crawler.screen_rules import learn_screen_rules_from_store  # noqa: E402
from crawler.x_scrape_playwright import fetch_best_public_tweet_text  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_full_tweet_text(tweet_id: str, username: str = "") -> str | None:
    """Longest tweet body: syndication tree + optional vxtwitter chain (see X_VXTWITTER_TEXT)."""
    return fetch_best_public_tweet_text(tweet_id, username)


def _load() -> dict:
    p = prompt_store_path()
    if not p.is_file():
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump({"updated_at": _now_iso(), "prompts": []}, f, ensure_ascii=False, indent=2)
            f.write("\n")
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def _load_rules() -> dict:
    if RULES_PATH.is_file():
        with RULES_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    return {"commercial_handles": [], "strip_phrases": [], "protected_phrases": [], "feedback_log": []}


def _save_rules(rules: dict) -> None:
    with RULES_PATH.open("w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _extract_handles_from_text(text: str) -> list[str]:
    """Find @handles in text that look commercial."""
    return [m.lower() for m in re.findall(r"@(\w+)", text)]


def _learn_from_feedback(store: dict) -> int:
    """Analyze all feedback and update trim_rules.json.

    - "trim_not_enough": extract @handles and leftover non-prompt fragments
      from the display_text and add them as strip rules.
    - "trim_too_hard": record the original text as protected so the trimmer
      doesn't cut it in future.
    - Custom strip_text from admin: add directly as a strip phrase.

    Returns count of new rules added.
    """
    rules = _load_rules()
    existing_handles = set(rules.get("commercial_handles", []))
    existing_strips = set(rules.get("strip_phrases", []))
    existing_protected = set(rules.get("protected_phrases", []))
    log = rules.get("feedback_log", [])
    new_rules = 0

    for p in store.get("prompts", []):
        fb = p.get("admin_feedback")
        if not fb:
            continue

        reason = fb.get("reason", "")
        action = fb.get("action", "")
        original_text = (p.get("text") or "").strip()
        current_display = (p.get("display_text") or "").strip()

        if action == "reject" and reason == "trim_not_enough":
            handles = _extract_handles_from_text(current_display)
            for h in handles:
                if h not in existing_handles and len(h) > 2:
                    existing_handles.add(h)
                    new_rules += 1

            strip_text = fb.get("strip_text", "").strip()
            if strip_text and strip_text not in existing_strips:
                existing_strips.add(strip_text)
                new_rules += 1

        elif action == "reject" and reason == "trim_too_hard":
            if original_text and current_display:
                removed = original_text.replace(current_display, "").strip()
                if removed and len(removed) > 20:
                    first_line = removed.split("\n")[0].strip()[:80]
                    if first_line and first_line not in existing_protected:
                        existing_protected.add(first_line)
                        new_rules += 1

    rules["commercial_handles"] = sorted(existing_handles)
    rules["strip_phrases"] = sorted(existing_strips)
    rules["protected_phrases"] = sorted(existing_protected)
    if new_rules > 0:
        log.append({
            "timestamp": _now_iso(),
            "new_rules": new_rules,
        })
        rules["feedback_log"] = log[-50:]
        _save_rules(rules)
        reload_learned()

    return new_rules


def _mark_retrim_pending_review(p: dict) -> None:
    """Re-trim changed body text; send row back to admin queue (null), not live hub."""
    p["published"] = None
    p.pop("admin_feedback", None)


def _retrim_from_feedback(store: dict) -> int:
    """Re-trim prompts based on their feedback.

    This runs AFTER _learn_from_feedback so the trimmer has the latest rules.
    Rows we touch go back to **pending** so they are reviewed again before publish.
    """
    touched = 0
    for p in store.get("prompts", []):
        fb = p.get("admin_feedback")
        if not fb or fb.get("action") != "reject":
            continue
        reason = fb.get("reason", "")
        # Prefer full tweet body; fall back to display when text was never backfilled.
        original = (p.get("text") or p.get("display_text") or "").strip()
        if not original:
            continue

        if reason == "incomplete_text":
            source_url = p.get("source_url", "")
            import re as _re
            m = _re.search(r"/status/(\d+)", source_url)
            if m:
                author = (p.get("author") or "").lstrip("@")
                full_text = _fetch_full_tweet_text(m.group(1), author)
                if full_text and len(full_text) > len(original):
                    p["text"] = full_text
                    p["tweet_text"] = full_text
                    p["display_text"] = trim_to_prompt_body(full_text)
                    _mark_retrim_pending_review(p)
                    touched += 1
                    continue
            p["display_text"] = trim_to_prompt_body(original)
            _mark_retrim_pending_review(p)
            touched += 1
        elif reason == "trim_too_hard":
            p["display_text"] = original
            _mark_retrim_pending_review(p)
            touched += 1
        elif reason == "trim_not_enough":
            p["display_text"] = trim_to_prompt_body(original)
            _mark_retrim_pending_review(p)
            touched += 1

    return touched


def _save(store: dict) -> None:
    data_path = prompt_store_path()
    backup = data_path.with_suffix(".json.bak")
    if data_path.exists():
        shutil.copy2(data_path, backup)
    save_store(store)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ADMIN_DIR), **kw)

    def do_GET(self):
        if self.path == "/api/prompts":
            data = json.dumps(_load(), ensure_ascii=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode())
            return
        if self.path == "/api/rules":
            data = json.dumps(_load_rules(), ensure_ascii=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode())
            return
        if self.path == "/" or self.path == "":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/save":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
                updates: list[dict] = payload.get("updates", [])
                store = _load()
                by_id = {p["id"]: p for p in store["prompts"]}
                changed = 0
                for u in updates:
                    pid = u.get("id")
                    if pid not in by_id:
                        continue
                    p = by_id[pid]
                    if "published" in u:
                        p["published"] = u["published"]
                    if "admin_feedback" in u:
                        p["admin_feedback"] = u["admin_feedback"]
                    changed += 1

                new_trim_rules = _learn_from_feedback(store)
                new_screen_rules = learn_screen_rules_from_store(store)
                retrimmed = _retrim_from_feedback(store)

                # Any trim-related reject in this save must leave the row pending for re-review,
                # even if _retrim skipped (edge cases) or an older admin process left published=false.
                trim_reasons = {"incomplete_text", "trim_too_hard", "trim_not_enough"}
                pending_unstick = 0
                for u in updates:
                    pid = u.get("id")
                    if not pid or pid not in by_id:
                        continue
                    fb = u.get("admin_feedback")
                    if not isinstance(fb, dict) or fb.get("action") != "reject":
                        continue
                    if fb.get("reason") not in trim_reasons:
                        continue
                    pr = by_id[pid]
                    if pr.get("published") is False:
                        pr["published"] = None
                        pr.pop("admin_feedback", None)
                        pending_unstick += 1

                _save(store)
                resp = json.dumps({
                    "ok": True,
                    "changed": changed,
                    "new_rules_learned": new_trim_rules,
                    "new_screen_rules": new_screen_rules,
                    "retrimmed": retrimmed,
                    "pending_unstick": pending_unstick,
                })
                self.send_response(200)
            except Exception as exc:
                resp = json.dumps({"ok": False, "error": str(exc)})
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp.encode())
            return
        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Admin server running at http://127.0.0.1:{PORT}")
    print(f"Prompt store: {prompt_store_path()}")
    print(f"Rules: {RULES_PATH}")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
