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

  const filtered = useMemo(() => {
    const rows = data?.prompts ?? [];
    const needle = q.trim().toLowerCase();
    let out: PromptRow[] = rows.filter((p) => {
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
  }, [data, q, cat, sort]);

  return (
    <div className="shell">
      <header className="top">
        <div>
          <h1 className="title">Seedance 2.0 Prompt Hub</h1>
          <p className="sub">
            Curated, scored prompts aggregated from X. Filter by category, search full text,
            and open the original post when available.
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
                {p.reviewed_llm ? (
                  <span className="badge llm mono" title="Refined with LLM review">
                    LLM reviewed
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
          <strong>How this works:</strong> GitHub Actions runs the Python crawler on a schedule.
          It ingests public posts from <strong>Bluesky</strong> and <strong>Mastodon</strong> ($0),
          optionally <strong>X</strong> if configured, extracts prompts, scores them, optionally
          refines with OpenAI, then commits <span className="mono">data/prompts.json</span>. This
          site is a static build from that file.
        </p>
        <p style={{ marginTop: "0.75rem" }}>
          <span className="mono">BLUESKY_IDENTIFIER</span> +{" "}
          <span className="mono">BLUESKY_APP_PASSWORD</span> power free Bluesky search.{" "}
          <span className="mono">TWITTER_BEARER_TOKEN</span> and{" "}
          <span className="mono">OPENAI_API_KEY</span> are optional.
        </p>
      </footer>
    </div>
  );
}
