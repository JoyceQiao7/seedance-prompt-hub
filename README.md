# Seedance 2.0 Prompt Hub

**Curated, high-quality prompts for Seedance 2.0 — updated daily.**

Powered by [Rizzbid](https://github.com/JoyceQiao7).

## What is this?

A free, open-source collection of the best Seedance 2.0 video generation prompts found across the internet. Every prompt is scored, screened, and categorized by use case so you can find exactly what you need.

## Browse prompts

**[joyceqiao7.github.io/seedance-prompt-hub](https://joyceqiao7.github.io/seedance-prompt-hub/)**

- Search by keyword
- Filter by use case — cinematic, commercial, music video, social/UGC, character, nature/scenic, VFX
- Every prompt links to its original source

New prompts are added automatically every day.

## Admin review (local)

The crawler reads learned rules from `data/trim_rules.json` and `data/screen_rules.json`. After you review prompts in the admin UI and click **Save changes**, those files are updated and the next crawl uses them.

1. From the repo root: `python admin/server.py`
2. Open [http://127.0.0.1:8090](http://127.0.0.1:8090) (override port with `ADMIN_PORT` if needed).
3. Approve or reject prompts. **Not a prompt (off target)** stores a fingerprint of that post (so duplicates are skipped) and an optional substring marker; it does **not** block the author.
4. Commit `data/prompts.json`, `data/trim_rules.json`, and `data/screen_rules.json` when you want the hub and CI crawls to pick up the changes.

## License

MIT
