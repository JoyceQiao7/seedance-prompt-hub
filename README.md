# Seedance / AI video prompt hub (X-only, unofficial scrape)

Daily automation that **searches X (Twitter)** for **AI video / creator**-adjacent posts (Seedance, Runway, Kling, Sora, text-to-video, etc.), **extracts prompts**, scores them, optionally runs **OpenAI** cleanup, merges into `data/prompts.json`, and publishes a **static search site** via GitHub Pages.

> **Important:** This uses **browser automation (Playwright)** and **session cookies** — not the official X API. That may **violate X’s Terms of Service**, can trigger **locks or captchas**, and **breaks when X changes the site**. You are responsible for compliance and risk. Use a **dedicated X account** and **low volume** (defaults are conservative).

## How the crawler works

1. **Playwright** opens Chromium (headless in CI), visits X **Search → Latest** for each query in `crawler/config.py` (`X_SCRAPE_QUERIES`).
2. Scrolls a few times per query, parses `article[data-testid="tweet"]` and `[data-testid="tweetText"]`.
3. Keeps posts that match **AI video / creator** heuristics (`crawler/relevance.py`).
4. **Extracts** prompt-like text (`crawler/extract_prompt.py`), **scores** and **categorizes**; optional **OpenAI** pass.
5. Dedupes by `x:{tweet_id}` and writes `data/prompts.json`.

## Session cookies (required for real data)

X usually shows a **login wall** for search automation. You must supply **logged-in** session data.

### Where is `X_COOKIES_JSON`?

It is **not** a file inside the Git repository. It is a **GitHub Actions secret** (encrypted settings on GitHub):

1. Open your repo: `https://github.com/JoyceQiao7/seedance-prompt-hub`
2. **Settings** → **Secrets and variables** → **Actions**
3. **New repository secret**
4. **Name:** `X_COOKIES_JSON`
5. **Secret:** paste your cookie JSON as **one line** (minified), or use secret **`X_COOKIES_B64`** with the whole JSON base64-encoded.

**Locally**, use a **file** instead (so you never commit secrets): copy `x_cookies.example.json` to `x_cookies.json`, replace the placeholders with real `auth_token` and `ct0` values, and set `X_COOKIES_PATH=./x_cookies.json` in `.env`. The real `x_cookies.json` is listed in `.gitignore`.

### Option A — Cookie JSON (good for GitHub Actions)

1. In **Chrome** or **Edge**, log into [x.com](https://x.com) with the **bot account**.
2. Open **DevTools** → **Application** → **Cookies** → `https://x.com`.
3. Copy values for at least **`auth_token`** and **`ct0`** (also set cookie `ct0` header parity — both are required historically for X web).
4. Build a **Playwright-style cookie list** (minimal example shape):

```json
[
  {
    "name": "auth_token",
    "value": "PASTE_VALUE",
    "domain": ".x.com",
    "path": "/",
    "secure": true,
    "httpOnly": true
  },
  {
    "name": "ct0",
    "value": "PASTE_VALUE",
    "domain": ".x.com",
    "path": "/",
    "secure": true
  }
]
```

5. Put the JSON in repo secret **`X_COOKIES_JSON`**, **or** base64 the entire JSON string and store as **`X_COOKIES_B64`** (helps with quoting/newlines).

**GitHub secret size limit** is about **48 KB** per secret. If you exceed it, trim to only essential cookies or use local `X_COOKIES_PATH` / `X_STORAGE_STATE_PATH`.

### Option B — Playwright `storage_state.json` (local / self-hosted)

1. Run a one-off Playwright script on your machine to log in and save `storage_state.json`, **or** export from a logged-in Chromium user data dir (advanced).
2. Point **`X_STORAGE_STATE_PATH`** at that file locally.  
   GitHub Actions cannot read your disk; for CI you still need **Option A** or a **self-hosted runner** with the file on disk.

### Local `.env`

```bash
cp .env.example .env
# set X_COOKIES_JSON='[...]' OR X_COOKIES_PATH=./cookies.json OR X_STORAGE_STATE_PATH=./state.json
PYTHONPATH=. python -m crawler
```

## GitHub Actions

Workflow: `.github/workflows/daily-update.yml`

**Secrets**

| Name | Purpose |
| --- | --- |
| `X_COOKIES_JSON` or `X_COOKIES_B64` | Logged-in session (see above) |
| `OPENAI_API_KEY` | Optional paid cleanup |

**Pages:** Settings → Pages → **GitHub Actions**.

### CI reliability note

GitHub-hosted runners use **datacenter IPs**. X may **challenge or block** them even with valid cookies. If the job consistently sees a **login wall**, use a **self-hosted runner**, run the crawler on a **home server** with `cron`, or lower frequency / fewer queries via env:

- `X_MAX_QUERIES` (default `10`)
- `X_MAX_SCROLLS` (default `7`)
- `X_SCROLL_PAUSE` (default `1.8` seconds)

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
PYTHONPATH=. python -m crawler
cd web && npm install && npm run dev
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `crawler/x_scrape_playwright.py` | Unofficial X Latest-tab scrape |
| `crawler/config.py` | Search query list |
| `data/prompts.json` | Dataset for the site |
| `web/` | React + Vite UI |

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This software is for **research and personal curation**. Scraping or automating X may breach **X’s Terms of Service** and applicable law in your jurisdiction. Prompt text belongs to original authors; this project **links** to source posts. **Rotate cookies** if leaked; use a **throwaway** X account for automation.
