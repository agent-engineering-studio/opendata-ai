export type ResourceSource =
  | "ckan"
  | "istat"
  | "eurostat"
  | "oecd"
  | "opencoesione"
  | "osm";

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
  /** When true, the backend biases the orchestrator toward geographic resources. */
  prefer_geo?: boolean;
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

/* ── Programma evidence-based (POST /programma — verticale PA) ──────────
 * Specchio del contratto Pydantic in
 * opendata-backend/src/opendata_backend/orchestrator/programma.py (spec 04 §6).
 */

export type FonteEvidenza =
  | "istat"
  | "opencoesione"
  | "ckan"
  | "eurostat"
  | "oecd"
  | "osm"
  | "ispra";

export type Evidenza = {
  fonte: FonteEvidenza;
  /** URL risolvibile — il cuore "verificabile": ogni claim ha la sua fonte cliccabile. */
  url: string;
  /** Cosa dice il dato (numeri inclusi), senza interpretazione. */
  dettaglio: string;
};

export type VoceSwot = {
  testo: string;
  evidenze: Evidenza[];
};

export type LivelloFattibilita = "alta" | "media" | "bassa" | "da_verificare";

export type Fattibilita = {
  livello: LivelloFattibilita;
  motivazione: string;
  /** Spend ratio storico del comune (da OpenCoesione), se disponibile. */
  spend_ratio_storico?: number | null;
};

export type Finanziamento = {
  linea: string;
  fonte_url: string;
  stato?: string | null;
};

export type Proposta = {
  titolo: string;
  descrizione: string;
  evidenze: Evidenza[];
  finanziamento?: Finanziamento | null;
  fattibilita: Fattibilita;
};

export type ProgrammaRequest = {
  /** Codice ISTAT del comune, es. "072006". */
  cod_comune: string;
  zona?: string | null;
  /** Tassonomia zona (Pezzo 6) — non esposta nel form finché il selettore non esiste. */
  zona_tipo?: string | null;
  zona_osm_id?: string | null;
  tema?: string | null;
  cicli?: string[] | null;
};

export type ProgrammaResponse = {
  comune: string;
  zona?: string | null;
  /** Chiavi: forze / debolezze / opportunita / minacce. */
  swot: Record<string, VoceSwot[]>;
  proposte: Proposta[];
  citazioni: Resource[];
  disclaimer: string;
  generato_il: string;
};
