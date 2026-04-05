export type ScreenMeta = {
  approved: boolean;
  score: number;
  reasons: string[];
  reviewed_at: string;
  engine: string;
};

export type PromptRow = {
  id: string;
  text: string;
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
};

export type PromptStore = {
  updated_at: string;
  prompts: PromptRow[];
};
