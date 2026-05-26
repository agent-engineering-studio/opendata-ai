import type { ResourceSource } from "./types";

export type ExampleQuery = {
  label: string;
  query: string;
  /** Hints which specialist agent owns the query — drives a coloured tag in the UI. */
  source?: ResourceSource | "cross";
};

export const EXAMPLE_QUERIES: ExampleQuery[] = [
  // ── CKAN — open-data portals ────────────────────────────────
  {
    source: "ckan",
    label: "5 dataset più recenti",
    query: "Mostrami i 5 dataset più recenti su dati.gov.it",
  },
  {
    source: "ckan",
    label: "Trasporti su data.gov.uk",
    query: "List recent datasets about transport",
  },
  {
    source: "ckan",
    label: "Dettagli di un dataset (UUID)",
    query:
      "Mostrami i dettagli del dataset 2908fe96-58c4-40fe-8b29-9d4d78715ba7",
  },
  {
    source: "ckan",
    label: "Organizzazioni per tema trasporti",
    query: "Quali organizzazioni pubblicano dati su trasporti?",
  },
  {
    source: "ckan",
    label: "Stato del portale CKAN",
    query: "Show CKAN portal status",
  },

  // ── ISTAT — statistica ufficiale italiana (SDMX) ────────────
  {
    source: "istat",
    label: "Popolazione residente per regione",
    query:
      "Popolazione residente per regione in Italia nel 2023 (dati ISTAT)",
  },
  {
    source: "istat",
    label: "Tasso di disoccupazione 2018-2023",
    query:
      "Andamento del tasso di disoccupazione in Italia dal 2018 al 2023, dati ISTAT",
  },
  {
    source: "istat",
    label: "PIL italiano per anno",
    query:
      "Mostra il PIL italiano per anno dal 2018, fonte ISTAT",
  },
  {
    source: "istat",
    label: "Dataflow ISTAT su mobilità",
    query:
      "Quali dataflow ISTAT sono disponibili sul tema mobilità e trasporti?",
  },
  {
    source: "istat",
    label: "Codici territoriali (NUTS Italia)",
    query:
      "Elenca i codici territoriali ISTAT di livello NUTS2 (regioni italiane)",
  },

  // ── Eurostat — statistica UE (opt-in: richiede ENABLE_EUROSTAT=true) ─
  {
    source: "eurostat",
    label: "PIL pro capite UE",
    query:
      "Confronta il PIL pro capite di Italia, Francia, Germania e Spagna negli ultimi 3 anni (dati Eurostat)",
  },
  {
    source: "eurostat",
    label: "Occupazione paesi UE",
    query:
      "Tasso di occupazione nei paesi UE-27 nel 2023, fonte Eurostat",
  },

  // ── OECD — statistica internazionale (opt-in: richiede ENABLE_OECD=true) ─
  {
    source: "oecd",
    label: "Spesa pubblica istruzione G7",
    query:
      "Spesa pubblica in istruzione come % del PIL nei paesi G7, fonte OECD",
  },
  {
    source: "oecd",
    label: "Indicatori OECD Italia",
    query:
      "Quali indicatori macroeconomici OECD sono disponibili per l'Italia?",
  },

  // ── Cross-source — fan-out vero su più specialisti ──────────
  {
    source: "cross",
    label: "ISTAT vs Toscana open data",
    query:
      "Popolazione della Toscana nel 2023: confronta i dati ufficiali ISTAT con quelli pubblicati sul portale open data regionale",
  },
];
