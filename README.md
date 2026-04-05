# Seedance 2.0 Prompt Hub

Fully automated, **$0-first** ingestion of **Seedance / SD2.x / ByteDance**-related prompts from **Bluesky** and **Mastodon**, with optional **X** (often paid) and optional **OpenAI** cleanup. Everything merges into `data/prompts.json` and ships as a **static search site** (categories + full-text search).

## Strategy ($0, low maintenance)

| Source | Cost | Automation | Notes |
| --- | --- | --- | --- |
| **Bluesky** (`app.bsky.feed.searchPosts`) | **$0** | Daily in GitHub Actions | Uses a **free Bluesky account** + **App Password** (not your login password). Official API, stable. |
| **Mastodon** (public hashtag timelines) | **$0** | Same job | Reads **public** posts from several large instances. **No token** if the instance allows anonymous tag reads; optional token if you hit `401`. |
| **X** (Recent Search) | Often **paid** | Optional | Enabled only if `TWITTER_BEARER_TOKEN` is set. Stops after **402** so logs stay quiet. |
| **OpenAI** | Paid per use | Optional | Improves cleanup; omit for strict **$0**. |

Posts must look **on-topic** (`seedance`, `bytedance`, `sd2`, etc.) before extraction—see `crawler/relevance.py`.

## How to get free Bluesky API credentials (App Password)

You need this for **fully automated** Bluesky search (recommended).

1. Create a free account at [https://bsky.app](https://bsky.app) (or sign in).
2. Open **Settings** → **Privacy and security** → **App passwords**.
3. Tap **Add app password**, give it a label (e.g. `prompt-hub`), **copy the generated password** once.  
   - This is **not** your normal Bluesky password.
4. Note your **handle** (e.g. `yourname.bsky.social`) — this is `BLUESKY_IDENTIFIER`.

Local `.env`:

```env
BLUESKY_IDENTIFIER=your.handle.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

GitHub Actions → **Settings** → **Secrets and variables** → **Actions** → add:

- `BLUESKY_IDENTIFIER`
- `BLUESKY_APP_PASSWORD`

Optional: `BLUESKY_PDS_HOST` (default `https://bsky.social`).

## Optional: Mastodon token (usually skip)

Many instances return public hashtag timelines **without** auth. If logs show empty Mastodon results and you know an instance requires login:

1. On that instance, create an account → **Preferences** → **Development** → **New Application** (read scope) → copy **access token**.
2. Set `MASTODON_ACCESS_TOKEN` locally or as a GitHub secret.

## Live site

With **GitHub Pages** source set to **GitHub Actions**, the workflow publishes something like:

`https://joyceqiao7.github.io/seedance-prompt-hub/`

## Local development

### Crawler

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add BLUESKY_IDENTIFIER + BLUESKY_APP_PASSWORD at minimum
PYTHONPATH=. python -m crawler
```

### Web UI

```bash
cd web
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173/`).

## GitHub Actions

Workflow: `.github/workflows/daily-update.yml`

- **Schedule**: daily **06:35 UTC** (edit cron to change).
- **Secrets**:
  - **Recommended ($0):** `BLUESKY_IDENTIFIER`, `BLUESKY_APP_PASSWORD`
  - **Optional:** `MASTODON_ACCESS_TOKEN`, `BLUESKY_PDS_HOST`
  - **Optional (often paid):** `TWITTER_BEARER_TOKEN`
  - **Optional (costs money):** `OPENAI_API_KEY`

**Pages:** **Settings** → **Pages** → **Build and deployment** → **GitHub Actions**.

## Repository layout

| Path | Purpose |
| --- | --- |
| `crawler/` | Bluesky + Mastodon + optional X; extract, score, optional LLM |
| `data/prompts.json` | Canonical dataset |
| `web/` | React + Vite UI |
| `.github/workflows/` | Daily automation + Pages deploy |

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

Respect each network’s **terms**, **automation**, and **rate** expectations. This project links to original posts; prompt text belongs to authors. **X** access must follow the [X Developer Agreement](https://developer.x.com/en/docs/developer-terms/agreement-and-policy). **Bluesky** and **Mastodon** have their own rules—use modest request volume (the daily job is designed to be light).
