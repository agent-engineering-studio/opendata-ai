export type ResourceSource =
  | "ckan"
  | "istat"
  | "eurostat"
  | "oecd"
  | "opencoesione"
  | "osm"
  | "kg";

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
  | "ispra"
  | "kg";

export type Evidenza = {
  /** Tag fonte normalizzato (istat, opencoesione, …) — string: il backend
   * tollera tag fuori lista pur di non perdere voci con URL validi. */
  fonte: FonteEvidenza | (string & {});
  /** URL risolvibile — il cuore "verificabile": ogni claim ha la sua fonte cliccabile. */
  url: string;
  /** Cosa dice il dato (numeri inclusi), senza interpretazione. */
  dettaglio: string;
  /** "certificato" = dato aperto ufficiale; "documentale" = documento comunale (KG). */
  tier?: "certificato" | "documentale";
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

export type Generatore =
  | "gap_comparativo"
  | "fabbisogno"
  | "incompiuto"
  | "finestra_finanziamento";

export type Proposta = {
  titolo: string;
  descrizione: string;
  evidenze: Evidenza[];
  finanziamento?: Finanziamento | null;
  fattibilita: Fattibilita;
  /** Modalità idee: da quale scarto nasce l'idea (assente in modalità scheda). */
  generatore?: Generatore | (string & {}) | null;
};

export type ModalitaProgramma = "scheda" | "idee" | "completa";

export type ProgrammaRequest = {
  /** Codice ISTAT del comune, es. "072006". */
  cod_comune: string;
  /** Nome del comune — serve agli specialisti che geocodificano (OSM). */
  comune_nome?: string | null;
  zona?: string | null;
  /** Tassonomia zona (Pezzo 6) — non esposta nel form finché il selettore non esiste. */
  zona_tipo?: string | null;
  zona_osm_id?: string | null;
  tema?: string | null;
  cicli?: string[] | null;
  /** "scheda" (default) = SWOT; "idee" = brainstorming a 4 generatori. */
  modalita?: ModalitaProgramma;
};

/* ── Selezione zona via tag OSM (Pezzo 6 — GET /territorio/*) ─────────── */

export type ZonaTipo =
  | "industriale"
  | "commerciale"
  | "portuale"
  | "centro_storico"
  | "verde"
  | "agricola";

export type ComuneMatch = {
  nome: string;
  /** Codice ISTAT zero-padded ("072006") — usabile come cod_comune ovunque. */
  ref_istat: string;
  cod_provincia?: string | null;
  osm_id: string;
  osm_url: string;
};

export type ZoneCandidate = {
  osm_type: string;
  /** "way/123" | "relation/456" — va in ProgrammaRequest.zona_osm_id. */
  osm_id: string;
  name: string | null;
  zona_tipo: string;
  area_m2: number;
  centroid: { lat: number; lon: number } | null;
  bbox: [number, number, number, number] | null;
  osm_url: string;
  geometry: unknown;
};

export type ZoneListResponse = {
  candidates: ZoneCandidate[];
  /** 1 = match per tag; 2 = fallback Nominatim; 3 = niente → livello comune. */
  fallback_level: 1 | 2 | 3;
  zona_tipo: string;
  ref_istat: string;
  source_url?: string;
};

export type ProgrammaResponse = {
  comune: string;
  zona?: string | null;
  /** Quadro descrittivo di apertura (prosa coi numeri chiave). */
  sintesi?: string;
  /** Chiavi: forze / debolezze / opportunita / minacce. */
  swot: Record<string, VoceSwot[]>;
  proposte: Proposta[];
  citazioni: Resource[];
  disclaimer: string;
  generato_il: string;
};
