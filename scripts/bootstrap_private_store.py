#!/usr/bin/env python3
"""Create private/data/prompts.json from the current dataset and refresh the public export.

Run once from the repo root after pulling::

    python scripts/bootstrap_private_store.py

Reads ``data/prompts.json`` (full or already-public). Writes:
- ``private/data/prompts.json`` — full snapshot (gitignored)
- ``data/prompts.json`` — public bundle (published only, no admin fields)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.merge_store import export_public_store, public_data_path, repo_root  # noqa: E402


def main() -> int:
    root = repo_root()
    pub_path = public_data_path()
    if not pub_path.is_file():
        print(f"Missing {pub_path}", file=sys.stderr)
        return 1

    with pub_path.open(encoding="utf-8") as f:
        store = json.load(f)

    private_path = root / "private" / "data" / "prompts.json"
    private_path.parent.mkdir(parents=True, exist_ok=True)
    with private_path.open("w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote full snapshot → {private_path}")

    exported = export_public_store(store)
    with pub_path.open("w", encoding="utf-8") as f:
        json.dump(exported, f, ensure_ascii=False, indent=2)
        f.write("\n")
    n = len(exported.get("prompts") or [])
    print(f"Public export → {pub_path} ({n} published prompts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
