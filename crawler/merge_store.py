"""Read/write aggregated prompt store."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def data_path() -> Path:
    return repo_root() / "data" / "prompts.json"


def load_store() -> dict[str, Any]:
    path = data_path()
    if not path.exists():
        return {"updated_at": _now_iso(), "prompts": []}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_store(store: dict[str, Any]) -> None:
    path = data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    store["updated_at"] = _now_iso()
    with path.open("w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
        f.write("\n")


def merge_items(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {p["id"]: p for p in existing if p.get("id")}
    for p in incoming:
        pid = p.get("id")
        if not pid:
            continue
        prev = by_id.get(pid)
        if prev is None or (p.get("quality_score", 0) >= prev.get("quality_score", 0)):
            by_id[pid] = p

    merged = list(by_id.values())
    merged.sort(
        key=lambda x: (
            x.get("quality_score", 0),
            x.get("created_at") or "",
        ),
        reverse=True,
    )
    return merged


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
