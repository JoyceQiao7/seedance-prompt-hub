# Seedance 2.0 Prompt Hub

**Curated, high-quality prompts for Seedance 2.0 — updated daily.**

Powered by [Rizzbid](https://github.com/JoyceQiao7).

## What is this?

A free, open-source collection of the best Seedance 2.0 video generation prompts found across the internet. Every prompt is scored, screened, and categorized by use case so you can find exactly what you need.

## Public vs private (this repo)

**Public (safe to push to GitHub)** — anyone can clone and reproduce the hub:

- `web/` — React UI, layout, and UX
- `data/prompts.json` — **published** prompts only (no `admin_feedback`, no unpublished rows)
- `data/trim_rules.json`, `data/screen_rules.json` — shared crawl/trim rules
- `crawler/` — scrape + merge pipeline used by scheduled CI
- `web/public/media/` — thumbnails and re-encoded videos referenced by the dataset
- `web/public/prompts.json` — copy of the public bundle for static hosting (updated by CI)
- `private.example/` — template for the maintainer-only tree (copy to `private/`)

**Private (gitignored `private/`)** — not on GitHub:

- Full prompt store (`private/data/prompts.json`): pending, rejected, and `admin_feedback`
- Admin app: copy `private.example/admin` → `private/admin` (see `private.example/README.md`)

GitHub Actions has no `private/` checkout: the crawler loads only the public `data/prompts.json`, **auto-publishes** new screened rows for that run, and commits the refreshed public bundle + media. Local runs **with** `private/data/prompts.json` keep the full queue and respect publish/reject decisions.

## Browse prompts

**[joyceqiao7.github.io/seedance-prompt-hub](https://joyceqiao7.github.io/seedance-prompt-hub/)**

- Search by keyword
- Filter by use case — cinematic, commercial, music video, social/UGC, character, nature/scenic, VFX
- Every prompt links to its original source

New prompts are added automatically every day.

## Run the hub locally

```bash
cd web
npm install
npm run dev
```

`npm run dev` / `npm run build` sync `data/prompts.json` into `web/public/prompts.json`.

## Maintainer: admin + private store

1. One-time: follow `private.example/README.md` (`bootstrap_private_store.py` + copy admin into `private/admin`).
2. `python private/admin/server.py` — open [http://127.0.0.1:8090](http://127.0.0.1:8090) (`ADMIN_PORT` overrides the port).
3. Saves update `private/data/prompts.json`, re-export `data/prompts.json`, and learned rules under `data/`.
4. Commit **public** paths: `data/prompts.json`, `data/trim_rules.json`, `data/screen_rules.json`, `web/public/prompts.json`, and `web/public/media/` as needed. Do not commit `private/`.

## License

MIT
