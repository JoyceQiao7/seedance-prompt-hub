# Private workspace (not on GitHub)

The `private/` directory is gitignored. It holds the **full** prompt store (pending, rejected, `admin_feedback`) and the admin UI.

## One-time setup

From the repository root:

```bash
mkdir -p private
cp -r private.example/admin private/admin
python scripts/bootstrap_private_store.py
```

The bootstrap script copies the current `data/prompts.json` into `private/data/prompts.json` (full snapshot), then rewrites `data/prompts.json` to the **public** export (published prompts only, no admin fields).

## Admin server

```bash
python private/admin/server.py
```

Open http://127.0.0.1:8090 — same as before, but data lives under `private/data/prompts.json` and each save refreshes `data/prompts.json` for Git + the static site.
