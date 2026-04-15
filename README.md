# Seedance 2.0 Prompt Hub

**Curated, high-quality prompts for Seedance 2.0 — updated daily.**

Powered by [Rizzbid](https://github.com/JoyceQiao7).

## What is this?

A free, open-source collection of the best Seedance 2.0 video generation prompts found across the internet. Every prompt is scored, screened, and categorized by use case so you can find exactly what you need.

## Repository layout

**Tracked in Git** — anyone can clone and reproduce the hub:

- `web/` — React UI (the hub only lists rows with `published: true`)
- `data/prompts.json` — **canonical** prompt store (published and pending review; `published` per row)
- `data/trim_rules.json`, `data/screen_rules.json` — shared crawl/trim rules
- `crawler/` — scrape + merge pipeline used by scheduled CI
- `web/public/media/` — thumbnails and re-encoded videos referenced by the dataset
- `web/public/prompts.json` — copy of `data/prompts.json` for static hosting (updated by CI / `npm run sync-data`)
- `admin/` — local review UI (`python admin/server.py`)

CI and local crawlers both read/write **`data/prompts.json`**. New crawled rows default to **`published: false`** until you approve them in admin.

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

## Maintainer: admin

1. From the repo root: `python admin/server.py` — open [http://127.0.0.1:8090](http://127.0.0.1:8090) (`ADMIN_PORT` overrides the port).
2. Saves update **`data/prompts.json`** (and `web/public/prompts.json` when present), plus learned rules under `data/`.
3. Commit `data/prompts.json`, `data/trim_rules.json`, `data/screen_rules.json`, `web/public/prompts.json`, and `web/public/media/` as needed.

## License

MIT
