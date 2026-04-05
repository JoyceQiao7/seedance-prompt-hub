# Seedance 2.0 Prompt Hub

**Open-source prompt library for AI video creators, powered by [Rizzbid](https://github.com/JoyceQiao7).**

Browse, search, and copy high-quality prompts built for **Seedance 2.0** and other leading AI video models. Updated daily from real creator posts on X.

**Live site** — [joyceqiao7.github.io/seedance-prompt-hub](https://joyceqiao7.github.io/seedance-prompt-hub/)

## What you get

- **Curated prompts** organized by use case — cinematic, commercial, music video, social/UGC, character, nature/scenic, VFX, and more.
- **Daily refresh** — a scheduled job finds new prompts from X, scores them, and publishes only the best.
- **Search and filter** — full-text search plus category filters so you find what you need fast.
- **Source links** — every prompt links to the original post for context, threads, and generated results.

## Use-case categories

| Category | What it covers |
| --- | --- |
| **Cinematic / Short film** | Narrative scenes, multi-shot storytelling, film grain, color grading, drama |
| **Commercial / Advertising** | Product shots, brand content, fashion, beauty, marketing |
| **Music video** | Performances, concerts, choreography, stage lighting, lip sync |
| **Social / UGC** | TikTok, Reels, vertical 9:16, POV, vlog-style, mobile footage |
| **Character** | Portraits, costumes, walk cycles, anime/3D characters |
| **Nature / Scenic** | Landscapes, aerials, drone shots, golden hour, wildlife, travel |
| **VFX / Effects** | Explosions, particles, magic, morphs, glitch, hologram |

## How it works

1. A **Playwright** crawler searches X for Seedance / AI-video-related posts (Latest tab).
2. Prompts are **extracted**, **scored** with heuristics, and passed through an **internal rule-based screen** (spam, noise, length, promo detection — no external API needed).
3. Only prompts scoring **≥ 90** and passing screening are shown publicly.
4. Categories are assigned automatically by keyword analysis.
5. Everything merges into `data/prompts.json` and deploys as a **static site** via GitHub Pages.

## For contributors

### Local setup

```bash
git clone https://github.com/JoyceQiao7/seedance-prompt-hub.git
cd seedance-prompt-hub
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
# Add X session cookies (see .env.example for details)
PYTHONPATH=. python -m crawler
cd web && npm install && npm run dev
```

### Session cookies

The crawler needs logged-in X cookies (`auth_token` + `ct0`). See `x_cookies.example.json` for the format. Copy it to `x_cookies.json` (gitignored) and fill in real values from DevTools.

For GitHub Actions, store the cookie JSON as a repository secret named **`X_COOKIES_JSON`** (or base64 it as **`X_COOKIES_B64`**).

### GitHub Actions

Workflow: `.github/workflows/daily-update.yml` — runs daily at 06:35 UTC or on manual dispatch.

**Settings → Pages → Source: GitHub Actions** to enable the live site.

### Environment variables

| Variable | Purpose |
| --- | --- |
| `X_COOKIES_JSON` / `X_COOKIES_B64` | Logged-in X session for search |
| `X_COOKIES_PATH` | Local path to cookie file (default: `./x_cookies.json`) |
| `X_MAX_QUERIES` | Number of search queries per run (default 10) |
| `X_MAX_SCROLLS` | Scrolls per query (default 7) |
| `X_SKIP_SCRAPE=1` | Skip browser; only merge + re-screen |
| `FORCE_SCREEN_BACKFILL=1` | Recompute screening for all rows |

### Repository layout

| Path | Purpose |
| --- | --- |
| `crawler/` | X scrape, extract, score, categorize, screen |
| `data/prompts.json` | Canonical dataset |
| `web/` | React + Vite frontend |
| `.github/workflows/` | Daily automation + Pages deploy |

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This project uses **browser automation** to read public X posts. That may conflict with X's Terms of Service; use at your own risk with a dedicated account and conservative settings. Prompt text belongs to the original authors — every entry links to the source post.

---

**Built with care by Rizzbid for the AI creator community.**
