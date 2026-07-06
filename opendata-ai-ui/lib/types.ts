export type ResourceSource =
  | "ckan"
  | "istat"
  | "eurostat"
  | "oecd"
  | "opencoesione"
  | "osm"
  | "mef"
  | "kg"
  | "web";

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
  /** Livello territoriale del dato (es. "comunale", "europeo") — trasparenza nei report. */
  livello?: string | null;
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
  | "kg"
  | "web";

export type Evidenza = {
  /** Tag fonte normalizzato (istat, opencoesione, …) — string: il backend
   * tollera tag fuori lista pur di non perdere voci con URL validi. */
  fonte: FonteEvidenza | (string & {});
  /** URL risolvibile — il cuore "verificabile": ogni claim ha la sua fonte cliccabile. */
  url: string;
  /** Cosa dice il dato (numeri inclusi), senza interpretazione. */
  dettaglio: string;
  /** "certificato" = dato aperto ufficiale; "documentale" = analisi precedente dal KG (riuso). */
  tier?: "certificato" | "documentale";
  /** Marketing (Pezzo 10): "dato_locale" = premessa locale verificabile;
   * "ispirazione_esterna" = precedente web di un altro ente (spunto, non prova). */
  fonte_tipo?: "dato_locale" | "ispirazione_esterna";
};

export type VoceSwot = {
  /** ID deterministico (content-hash) timbrato server-side, es. `swot_ab12cd34`. */
  id?: string;
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

/** Generatori del marketing territoriale (Pezzo 10). */
export type GeneratoreMarketing =
  | "caso_analogo"
  | "asset_sottoutilizzato"
  | "domanda_emergente";

/** Lenti tematiche del marketing territoriale (Pezzo 10). */
export type LenteMarketing =
  | "turismo_cultura"
  | "viabilita_mobilita"
  | "sicurezza_vivibilita"
  | "attrattivita_brand";

export type Proposta = {
  /** ID deterministico (content-hash) timbrato server-side, es. `idea_ab12cd34`. */
  id?: string;
  titolo: string;
  descrizione: string;
  evidenze: Evidenza[];
  finanziamento?: Finanziamento | null;
  fattibilita: Fattibilita;
  /** Modalità idee/marketing: da quale scarto/generatore nasce (assente in scheda). */
  generatore?: Generatore | GeneratoreMarketing | (string & {}) | null;
  /** Modalità marketing: lente tematica per il raggruppamento nella sezione dedicata. */
  lente?: LenteMarketing | (string & {}) | null;
};

export type ModalitaProgramma = "scheda" | "idee" | "completa" | "marketing";

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
  /** "Rigenera": salta la cache (F1) e forza un nuovo fan-out. */
  force_refresh?: boolean;
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
  /** Lettura d'insieme delle idee: leve principali + idee più promettenti. */
  idee_sintesi?: string;
  /** Chiavi: forze / debolezze / opportunita / minacce. */
  swot: Record<string, VoceSwot[]>;
  proposte: Proposta[];
  citazioni: Resource[];
  disclaimer: string;
  generato_il: string;
  /** True se la scheda arriva dalla cache (F1): la UI offre "Rigenera". */
  da_cache?: boolean;
};
