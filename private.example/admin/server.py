"""Local admin server (maintainer-only): full store under private/, public export to data/.

Copy this tree to ``private/admin`` (see ``private.example/README.md``), then from repo root::

    python private/admin/server.py

Open: http://localhost:8090

On save:
1. Writes the full store (published + unpublished + admin_feedback) to ``private/data/prompts.json``
2. Exports the public bundle to ``data/prompts.json`` (published-only, no admin fields)
3. Learns trim / screen rules under ``data/``
4. Copies the public bundle to ``web/public/prompts.json`` for local preview
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

ROOT = Path(__file__).resolve().parents[2]
ADMIN_DIR = Path(__file__).resolve().parent
RULES_PATH = ROOT / "data" / "trim_rules.json"
PORT = int(os.environ.get("ADMIN_PORT", "8090"))

sys.path.insert(0, str(ROOT))
from crawler.merge_store import write_public_prompts_json  # noqa: E402
from crawler.prompt_trimmer import reload_learned, trim_to_prompt_body  # noqa: E402
from crawler.screen_rules import learn_screen_rules_from_store  # noqa: E402
from crawler.x_scrape_playwright import fetch_best_public_tweet_text  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _admin_data_path() -> Path:
    """Full store path; bootstrap from ``data/prompts.json`` on first run."""
    dest = ROOT / "private" / "data" / "prompts.json"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        pub = ROOT / "data" / "prompts.json"
        if pub.is_file():
            shutil.copy2(pub, dest)
        else:
            with dest.open("w", encoding="utf-8") as f:
                json.dump({"updated_at": _now_iso(), "prompts": []}, f, ensure_ascii=False, indent=2)
                f.write("\n")
    return dest


def _fetch_full_tweet_text(tweet_id: str, username: str = "") -> str | None:
    """Longest tweet body: syndication tree + optional vxtwitter chain (see X_VXTWITTER_TEXT)."""
    return fetch_best_public_tweet_text(tweet_id, username)


def _load() -> dict:
    with _admin_data_path().open(encoding="utf-8") as f:
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


def _retrim_from_feedback(store: dict) -> int:
    """Re-trim prompts based on their feedback.

    This runs AFTER _learn_from_feedback so the trimmer has the latest rules.
    """
    touched = 0
    for p in store.get("prompts", []):
        fb = p.get("admin_feedback")
        if not fb or fb.get("action") != "reject":
            continue
        reason = fb.get("reason", "")
        original = (p.get("text") or "").strip()
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
                    touched += 1
                    continue
            p["display_text"] = trim_to_prompt_body(original)
            touched += 1
        elif reason == "trim_too_hard":
            p["display_text"] = original
            touched += 1
        elif reason == "trim_not_enough":
            p["display_text"] = trim_to_prompt_body(original)
            touched += 1

    return touched


def _save(store: dict) -> None:
    store["updated_at"] = _now_iso()
    data_path = _admin_data_path()
    backup = data_path.with_suffix(".json.bak")
    if data_path.exists():
        shutil.copy2(data_path, backup)
    with data_path.open("w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
        f.write("\n")
    write_public_prompts_json(store)
    web_public = ROOT / "web" / "public" / "prompts.json"
    if web_public.parent.exists():
        shutil.copy2(ROOT / "data" / "prompts.json", web_public)


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

                _save(store)
                resp = json.dumps({
                    "ok": True,
                    "changed": changed,
                    "new_rules_learned": new_trim_rules,
                    "new_screen_rules": new_screen_rules,
                    "retrimmed": retrimmed,
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
    print(f"Admin server running at http://localhost:{PORT}")
    print(f"Full store: {_admin_data_path()}")
    print(f"Public export: {ROOT / 'data' / 'prompts.json'}")
    print(f"Rules: {RULES_PATH}")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
