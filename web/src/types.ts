export type ScreenMeta = {
  approved: boolean;
  score: number;
  reasons: string[];
  reviewed_at: string;
  engine: string;
};

export type AdminFeedback = {
  action: "approve" | "reject";
  reason?: string | null;
  note?: string | null;
  /** Optional substring that marks non-prompt content (off_target only; min length enforced server-side). */
  block_phrase?: string | null;
  /** Optional phrase to strip when trim was not aggressive enough. */
  strip_text?: string | null;
  timestamp: string;
};

export type PromptRow = {
  id: string;
  text: string;
  display_text?: string | null;
  category: string;
  quality_score: number;
  source_url: string;
  author: string;
  created_at: string | null;
  tweet_text?: string | null;
  source_network?: string | null;
  reviewed_llm?: boolean;
  likes?: number | null;
  retweets?: number | null;
  screen?: ScreenMeta | null;
  published?: boolean | null;
  admin_feedback?: AdminFeedback | null;
  video_url?: string | null;
  thumbnail?: string | null;
  video?: string | null;
};

export type PromptStore = {
  updated_at: string;
  prompts: PromptRow[];
};
