export type PromptRow = {
  id: string;
  text: string;
  category: string;
  quality_score: number;
  source_url: string;
  author: string;
  created_at: string | null;
  tweet_text?: string | null;
  reviewed_llm?: boolean;
  likes?: number | null;
  retweets?: number | null;
};

export type PromptStore = {
  updated_at: string;
  prompts: PromptRow[];
};
