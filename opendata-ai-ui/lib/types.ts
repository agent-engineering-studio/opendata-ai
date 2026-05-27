export type ResourceSource = "ckan" | "istat" | "eurostat" | "oecd";

export type Resource = {
  name: string;
  url: string;
  format: string;
  content: string | null;
  source?: ResourceSource | null;
  /** Optional human description of the dataset (from the portal / dataflow). */
  description?: string | null;
  /** Self-contained Leaflet+OSM HTML map (rendered by osm-mcp) for GeoJSON resources. */
  preview_html?: string | null;
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
