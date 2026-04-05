import { useEffect, useMemo, useState } from "react";
import type { PromptRow, PromptStore } from "./types";

const CATEGORIES = [
  "all",
  "cinematic",
  "commercial",
  "music-video",
  "social-content",
  "character",
  "nature-scenic",
  "vfx",
  "other",
] as const;

const CATEGORY_LABELS: Record<string, string> = {
  all: "All categories",
  cinematic: "Cinematic / Short film",
  commercial: "Commercial / Advertising",
  "music-video": "Music video",
  "social-content": "Social / UGC",
  character: "Character",
  "nature-scenic": "Nature / Scenic",
  vfx: "VFX / Effects",
  other: "Other",
};

const MIN_PUBLIC_QUALITY = 90;

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
  const [sort, setSort] = useState<"relevance" | "date">("relevance");

  const filtered = useMemo(() => {
    const rows = data?.prompts ?? [];
    const needle = q.trim().toLowerCase();
    let out: PromptRow[] = rows.filter((p) => {
      if (p.quality_score < MIN_PUBLIC_QUALITY) return false;
      if (p.screen?.approved === false) return false;
      if (cat !== "all" && p.category !== cat) return false;
      if (!needle) return true;
      const hay = `${p.text} ${p.author} ${p.category}`.toLowerCase();
      return hay.includes(needle);
    });
    out = [...out].sort((a, b) => {
      if (sort === "relevance") {
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
            Discover ready-to-use prompts for <strong>Seedance 2.0</strong> and other AI video
            models. Search by use case, browse categories, and jump straight to the source.
          </p>
        </div>
        <div className="pill mono">
          <span>Powered by <strong>Rizzbid</strong></span>
          <span className="sep">·</span>
          <span>Updated daily</span>
        </div>
      </header>

      {error ? <div className="err">{error}</div> : null}

      <section className="controls" aria-label="Search and filters">
        <div className="field">
          <label htmlFor="q">Search prompts</label>
          <input
            id="q"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Try: cinematic, drone, neon, portrait, explosion…"
            autoComplete="off"
          />
        </div>
        <div className="field">
          <label htmlFor="cat">Use case</label>
          <select
            id="cat"
            value={cat}
            onChange={(e) => setCat(e.target.value as (typeof CATEGORIES)[number])}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c] ?? c}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="sort">Sort</label>
          <select
            id="sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as "relevance" | "date")}
          >
            <option value="relevance">Most relevant</option>
            <option value="date">Newest first</option>
          </select>
        </div>
      </section>

      <div className="meta">
        <span>
          <strong style={{ color: "var(--text)" }}>{filtered.length}</strong> prompts
        </span>
        {data?.updated_at ? (
          <span>
            Last updated <span className="mono">{data.updated_at.slice(0, 10)}</span>
          </span>
        ) : null}
      </div>

      {!data && !error ? (
        <div className="empty">Loading prompts…</div>
      ) : filtered.length === 0 ? (
        <div className="empty">No prompts match your search. Try a different keyword or category.</div>
      ) : (
        <div className="grid">
          {filtered.map((p) => (
            <article key={p.id} className="card">
              <div className="card-head">
                <span className="badge cat mono">{CATEGORY_LABELS[p.category] ?? p.category}</span>
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
                  View on X →
                </a>
              </div>
            </article>
          ))}
        </div>
      )}

      <footer className="hint">
        <p>
          Prompts are collected daily from <strong>X</strong>, scored and screened automatically,
          then published here. Only top-quality prompts make it to this page. Every card links
          back to the original post so you can see the full thread and results.
        </p>
        <p style={{ marginTop: "0.75rem" }}>
          Open source — built by{" "}
          <a href="https://github.com/JoyceQiao7/seedance-prompt-hub" target="_blank" rel="noreferrer">
            Rizzbid
          </a>
          .
        </p>
      </footer>
    </div>
  );
}
