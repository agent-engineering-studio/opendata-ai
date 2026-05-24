export type Resource = {
  name: string;
  url: string;
  format: string;
  content: string | null;
};

export type ChatRequest = {
  query: string;
  base_url?: string;
};

export type ChatResponse = {
  text: string;
  resources: Resource[];
};

export type ChatMessage =
  | { role: "user"; text: string }
  | {
      role: "assistant";
      text: string;
      resources: Resource[];
      durationMs: number;
    }
  | { role: "error"; text: string };
