import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

const PROMPT_PREVIEW_LEN = 180;
/** First N grid thumbnails load eagerly with high fetch priority (above-the-fold on typical layouts). */
const THUMB_GRID_PRIORITY_COUNT = 18;

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

/** When `enabled`, flip to true once the element nears the viewport (分段 / staged load). */
function useIntersectOnce<T extends HTMLElement>(enabled: boolean, rootMargin = "200px") {
  const ref = useRef<T | null>(null);
  const [ready, setReady] = useState(() => !enabled);

  useEffect(() => {
    if (!enabled) return;
    if (ready) return;
    const node = ref.current;
    if (!node) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setReady(true);
            io.disconnect();
            break;
          }
        }
      },
      { rootMargin, threshold: 0.01 },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [enabled, ready, rootMargin]);

  return [ref, ready] as const;
}

function mediaUrl(relPath: string): string {
  return new URL(relPath, window.location.origin + import.meta.env.BASE_URL).toString();
}

/** Local path under public/ or absolute CDN URL from the dataset. */
function absoluteMediaRef(ref: string): string {
  const s = ref.trim();
  if (/^https?:\/\//i.test(s)) return s;
  return mediaUrl(s);
}

function PlayOverlayIcon() {
  return (
    <div className="play-overlay" aria-label="Play video">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <circle cx="24" cy="24" r="24" fill="rgba(0,0,0,0.55)" />
        <path d="M19 14l16 10-16 10V14z" fill="#fff" />
      </svg>
    </div>
  );
}

function rowHasVideoPreview(p: PromptRow): boolean {
  return !!(
    (p.thumbnail && p.thumbnail.trim()) ||
    (p.video && p.video.trim()) ||
    (p.video_url && p.video_url.trim())
  );
}

/* ── Modal ── */

function PromptModal({
  p,
  onClose,
}: {
  p: PromptRow;
  onClose: () => void;
}) {
  const displayText = p.display_text || p.text;
  const [copied, setCopied] = useState(false);
  const backdropRef = useRef<HTMLDivElement>(null);

  const hasThumb = !!(p.thumbnail && p.thumbnail.trim());
  const playSrc =
    p.video && p.video.trim()
      ? absoluteMediaRef(p.video)
      : p.video_url && p.video_url.trim()
        ? absoluteMediaRef(p.video_url)
        : null;
  const hasModalMedia = hasThumb || !!playSrc;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(displayText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [displayText]);

  return (
    <div
      className="modal-backdrop"
      ref={backdropRef}
      onClick={(e) => {
        if (e.target === backdropRef.current) onClose();
      }}
    >
      <div className="modal">
        <button className="modal-close" onClick={onClose} aria-label="Close">
          ✕
        </button>
        <div className="modal-body">
          {hasModalMedia && (
            <div className="modal-media">
              {playSrc ? (
                <video
                  src={playSrc}
                  poster={hasThumb ? absoluteMediaRef(p.thumbnail!) : undefined}
                  controls
                  autoPlay
                  playsInline
                  preload="metadata"
                  controlsList="nodownload"
                />
              ) : (
                <img
                  src={absoluteMediaRef(p.thumbnail!)}
                  alt={`Preview for ${p.category} prompt by ${p.author}`}
                  loading="eager"
                  decoding="async"
                  fetchPriority="high"
                />
              )}
            </div>
          )}
          <div className="modal-content">
            <div className="card-head">
              <span className="badge cat mono">
                {CATEGORY_LABELS[p.category] ?? p.category}
              </span>
              <button
                className="copy-btn mono"
                onClick={handleCopy}
                title="Copy prompt"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
            <pre className="prompt-body mono modal-prompt">{displayText}</pre>
            <div className="footer">
              <span>{p.author}</span>
              <a href={p.source_url} target="_blank" rel="noreferrer">
                View on X →
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Card ── */

function PromptCard({
  p,
  onOpen,
  thumbBoost,
}: {
  p: PromptRow;
  onOpen: () => void;
  /** When true, thumbnail loads with high priority (first visible rows). */
  thumbBoost: boolean;
}) {
  const displayText = p.display_text || p.text;
  const isLong = displayText.length > PROMPT_PREVIEW_LEN;
  const preview = isLong
    ? displayText.slice(0, PROMPT_PREVIEW_LEN).trimEnd() + "…"
    : displayText;

  const hasThumb = !!(p.thumbnail && p.thumbnail.trim());
  const hasLocalVideo = !!(p.video && p.video.trim());
  const hasRemoteVideo = !!(p.video_url && p.video_url.trim());
  const showPlay = hasLocalVideo || hasRemoteVideo;
  const previewLabel = `Preview for ${p.category} prompt by ${p.author}`;
  /** Local file only: defer <video> until near viewport. Remote URLs never load in the grid (modal only). */
  const deferGridVideo = hasLocalVideo && !hasThumb;
  const [mediaRef, gridVideoReady] = useIntersectOnce<HTMLElement>(deferGridVideo, "220px");

  return (
    <article className="card" onClick={onOpen}>
      <figure className="card-media" ref={mediaRef}>
        {hasThumb ? (
          <>
            <img
              src={absoluteMediaRef(p.thumbnail!)}
              alt={previewLabel}
              width={480}
              height={270}
              loading={thumbBoost ? "eager" : "lazy"}
              decoding="async"
              fetchPriority={thumbBoost ? "high" : "auto"}
            />
          </>
        ) : deferGridVideo ? (
          gridVideoReady ? (
            <video
              src={`${absoluteMediaRef(p.video!)}#t=0.001`}
              muted
              playsInline
              preload="metadata"
              width={480}
              height={270}
              aria-label={previewLabel}
            />
          ) : (
            <div className="card-media-skeleton" aria-hidden />
          )
        ) : (
          <div className="card-media-skeleton" aria-hidden />
        )}
        {showPlay ? <PlayOverlayIcon /> : null}
      </figure>
      <div className="card-head">
        <span className="badge cat mono">
          {CATEGORY_LABELS[p.category] ?? p.category}
        </span>
      </div>
      <p className="prompt-body mono prompt-preview">{preview}</p>
      <div className="footer">
        <span>{p.author}</span>
        <span className="view-more">View →</span>
      </div>
    </article>
  );
}

/* ── App ── */

export default function App() {
  const { data, error } = usePromptStore();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<(typeof CATEGORIES)[number]>("all");
  const [sort, setSort] = useState<"trending" | "date">("trending");
  const [activePrompt, setActivePrompt] = useState<PromptRow | null>(null);

  const filtered = useMemo(() => {
    const rows = data?.prompts ?? [];
    const needle = q.trim().toLowerCase();
    let out: PromptRow[] = rows.filter((p) => {
      if (p.published !== true) return false;
      if (!rowHasVideoPreview(p)) return false;
      if (cat !== "all" && p.category !== cat) return false;
      if (!needle) return true;
      const hay = `${p.display_text ?? p.text} ${p.author} ${p.category}`.toLowerCase();
      return hay.includes(needle);
    });
    out = [...out].sort((a, b) => {
      if (sort === "trending") {
        const likeDiff = (b.likes ?? 0) - (a.likes ?? 0);
        if (likeDiff !== 0) return likeDiff;
      }
      const da = (a.created_at ?? "").localeCompare(b.created_at ?? "");
      return -da;
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
            onChange={(e) => setSort(e.target.value as "trending" | "date")}
          >
            <option value="trending">Most trending</option>
            <option value="date">Newest first</option>
          </select>
        </div>
      </section>

      <div className="meta">
        <span>
          <strong style={{ color: "var(--text)" }}>{filtered.length}</strong> prompts
        </span>
      </div>

      {!data && !error ? (
        <div className="empty">Loading prompts…</div>
      ) : filtered.length === 0 ? (
        <div className="empty">No prompts match your search. Try a different keyword or category.</div>
      ) : (
        <div className="grid">
          {filtered.map((p, i) => (
            <PromptCard
              key={p.id}
              p={p}
              thumbBoost={i < THUMB_GRID_PRIORITY_COUNT}
              onOpen={() => setActivePrompt(p)}
            />
          ))}
        </div>
      )}

      <footer className="hint">
        <p>
          Open source — built by{" "}
          <a href="https://github.com/JoyceQiao7/seedance-prompt-hub" target="_blank" rel="noreferrer">
            Rizzbid
          </a>
          .
        </p>
      </footer>

      {activePrompt && (
        <PromptModal p={activePrompt} onClose={() => setActivePrompt(null)} />
      )}
    </div>
  );
}
