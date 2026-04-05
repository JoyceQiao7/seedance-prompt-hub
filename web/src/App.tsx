import { useEffect, useMemo, useState } from "react";
import type { PromptRow, PromptStore } from "./types";

const CATEGORIES = [
  "all",
  "motion",
  "camera",
  "character",
  "scene",
  "style",
  "lighting",
  "audio",
  "other",
] as const;

const LISTING = ["published", "all", "held"] as const;

function passesListing(p: PromptRow, mode: (typeof LISTING)[number]): boolean {
  const approved = p.screen?.approved;
  if (mode === "published") return approved !== false;
  if (mode === "held") return approved === false;
  return true;
}

function usePromptStore() {
  const [data, setData] = useState<PromptStore | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const url = new URL("prompts.json", window.location.origin + import.meta.env.BASE_URL);
    fetch(url.toString())
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load prompts (${r.status})`);
        return r.json();
      })
      .then((j: PromptStore) => setData(j))
      .catch((e: Error) => setError(e.message));
  }, []);

  return { data, error };
}

export default function App() {
  const { data, error } = usePromptStore();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<(typeof CATEGORIES)[number]>("all");
  const [sort, setSort] = useState<"quality" | "date">("quality");
  const [listing, setListing] = useState<(typeof LISTING)[number]>("published");

  const filtered = useMemo(() => {
    const rows = data?.prompts ?? [];
    const needle = q.trim().toLowerCase();
    let out: PromptRow[] = rows.filter((p) => {
      if (!passesListing(p, listing)) return false;
      if (cat !== "all" && p.category !== cat) return false;
      if (!needle) return true;
      const hay = `${p.text} ${p.author} ${p.tweet_text ?? ""}`.toLowerCase();
      return hay.includes(needle);
    });
    out = [...out].sort((a, b) => {
      if (sort === "quality") {
        const dq = (b.quality_score ?? 0) - (a.quality_score ?? 0);
        if (dq !== 0) return dq;
      }
      const da = (a.created_at ?? "").localeCompare(b.created_at ?? "");
      return sort === "date" ? -da : da;
    });
    return out;
  }, [data, q, cat, sort, listing]);

  return (
    <div className="shell">
      <header className="top">
        <div>
          <h1 className="title">Seedance 2.0 Prompt Hub</h1>
          <p className="sub">
            Prompts from X are scored, then passed through an <strong>internal rule-based screen</strong>{" "}
            (no cloud LLM). Browse published items or switch to <strong>All / Held back</strong> for review.
          </p>
        </div>
        <div className="pill mono">Daily refresh · Open source</div>
      </header>

      {error ? <div className="err">{error}</div> : null}

      <section className="controls" aria-label="Search and filters">
        <div className="field">
          <label htmlFor="q">Search</label>
          <input
            id="q"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Try: dolly, neon, macro, golden hour…"
            autoComplete="off"
          />
        </div>
        <div className="field">
          <label htmlFor="cat">Category</label>
          <select
            id="cat"
            value={cat}
            onChange={(e) => setCat(e.target.value as (typeof CATEGORIES)[number])}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c === "all" ? "All categories" : c}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="sort">Sort</label>
          <select
            id="sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as "quality" | "date")}
          >
            <option value="quality">Quality score</option>
            <option value="date">Newest first</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="listing">Listing</label>
          <select
            id="listing"
            value={listing}
            onChange={(e) => setListing(e.target.value as (typeof LISTING)[number])}
          >
            <option value="published">Published (screen approved)</option>
            <option value="all">All (internal review)</option>
            <option value="held">Held back only</option>
          </select>
        </div>
      </section>

      <div className="meta">
        <span>
          Showing <strong style={{ color: "var(--text)" }}>{filtered.length}</strong> prompts
        </span>
        {data?.updated_at ? (
          <span>
            Dataset updated <span className="mono">{data.updated_at}</span>
          </span>
        ) : null}
      </div>

      {!data && !error ? (
        <div className="empty">Loading prompts…</div>
      ) : filtered.length === 0 ? (
        <div className="empty">No prompts match these filters.</div>
      ) : (
        <div className="grid">
          {filtered.map((p) => (
            <article key={p.id} className="card">
              <div className="card-head">
                <span className="badge mono">{p.category}</span>
                <span className="badge score mono">score {p.quality_score}</span>
                {p.source_network ? (
                  <span className="badge mono" title="Origin network">
                    {p.source_network}
                  </span>
                ) : null}
                {p.screen ? (
                  <span
                    className={`badge mono ${p.screen.approved ? "screen-ok" : "screen-hold"}`}
                    title={
                      p.screen.reasons.length
                        ? `Screen: ${p.screen.reasons.join(", ")}`
                        : "Internal screen"
                    }
                  >
                    screen {p.screen.score}
                    {p.screen.approved ? "" : " · held"}
                  </span>
                ) : null}
              </div>
              <p className="prompt-body mono">{p.text}</p>
              <div className="footer">
                <span>
                  {p.author}
                  {p.created_at ? (
                    <>
                      {" · "}
                      <span className="mono">{p.created_at.slice(0, 10)}</span>
                    </>
                  ) : null}
                </span>
                <a href={p.source_url} target="_blank" rel="noreferrer">
                  View source →
                </a>
              </div>
            </article>
          ))}
        </div>
      )}

      <footer className="hint">
        <p>
          <strong>How this works:</strong> A <strong>Playwright</strong> job searches <strong>X</strong>{" "}
          (Latest) for AI-video-related queries, extracts prompts, scores them, then runs an{" "}
          <strong>internal screen</strong> (spam, length, link/hashtag noise, promo patterns—no OpenAI).
          Published rows have <span className="mono">screen.approved: true</span>. Data lives in{" "}
          <span className="mono">data/prompts.json</span>.
        </p>
        <p style={{ marginTop: "0.75rem" }}>
          CI needs <span className="mono">X_COOKIES_JSON</span> / <span className="mono">X_COOKIES_B64</span>.
          Set <span className="mono">X_SKIP_SCRAPE=1</span> locally to only backfill screening.
        </p>
      </footer>
    </div>
  );
}
