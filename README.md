# Seedance 2.0 Prompt Hub

Daily-curated **Seedance / SD2.0** video prompts discovered on **X** (Twitter), scored for quality, optionally refined with an LLM, and published as a **searchable static site** (category + full-text search).

## Live site

After you enable **GitHub Pages → GitHub Actions** on the repository, the workflow publishes the latest build. The URL will look like:

`https://joyceqiao7.github.io/seedance-prompt-hub/`

(Exact path matches the repository name.)

## How it works

1. **Crawler** (`crawler/`) calls **X API v2 Recent Search** with queries around Seedance / SD2.0, skips pure retweets, and pulls English posts.
2. **Extraction** finds the actual prompt inside the tweet (labels like `Prompt:`, quotes, fenced blocks, or dense descriptive text).
3. **Heuristic scoring** ranks usefulness (length, structure, camera/motion vocabulary, spam penalties).
4. **Optional review**: if `OPENAI_API_KEY` is set, new high-scoring rows are sent to **GPT-4o-mini** (configurable) to normalize text, assign category, and veto junk (`keep: false`).
5. **Store**: everything merges into `data/prompts.json` (deduped by tweet id, highest score wins).
6. **Website** (`web/`): Vite + React loads `prompts.json`, with filters for **category** and **sort** (quality vs date).

> **X API access**: Recent search requires a developer project with appropriate access. If the token is missing in CI, the job still runs and keeps existing data—so the site never goes empty.

## Local development

### Crawler

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill TWITTER_BEARER_TOKEN (and optionally OPENAI_API_KEY)
PYTHONPATH=. python -m crawler
```

### Web UI

```bash
cd web
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173/`). `npm run dev` syncs `data/prompts.json` into `web/public/prompts.json` first.

## GitHub Actions

Workflow: `.github/workflows/daily-update.yml`

- **Schedule**: every day at **06:35 UTC** (adjust the cron as you like).
- **Secrets** (repository → Settings → Secrets):
  - `TWITTER_BEARER_TOKEN` — required for fresh pulls from X.
  - `OPENAI_API_KEY` — optional; improves cleanup and categorization.

**Pages**: Repository → **Settings** → **Pages** → **Build and deployment** → Source: **GitHub Actions**.

The workflow commits updates to `data/prompts.json` with `[skip ci]` to avoid recursive runs.

## Repository layout

| Path | Purpose |
| --- | --- |
| `crawler/` | X fetch, extract, score, optional LLM, merge |
| `data/prompts.json` | Canonical dataset consumed by the site |
| `web/` | React + Vite frontend |
| `.github/workflows/` | Daily automation + Pages deploy |

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This project uses the **official X API** only. Automated collection must comply with [X Developer Agreement](https://developer.x.com/en/docs/developer-terms/agreement-and-policy) and rate limits. Prompts belong to their original authors; this hub is an index with attribution links.
