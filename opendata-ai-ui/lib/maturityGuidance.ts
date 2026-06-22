/*
 * Aggancia i risultati della maturità open data alla guida operativa
 * (`/guida-open-data`). Un solo punto di verità per:
 *   - il link alla pagina guida (disclaimer per gli enti a 0 / "dato insufficiente");
 *   - la mappatura codice-raccomandazione → sezione della guida + consiglio sintetico,
 *     così ogni gap evidenziato dalla scorecard porta a "come ridurlo o eliminarlo".
 *
 * I `code` provengono dal motore di scoring (opendata_core/maturity/scoring.py):
 * no_open_data, open_license, open_format, freshness, dcat_ap_it, hvd,
 * sector_gap, hvd_coverage.
 */

export const GUIDA_PATH = "/guida-open-data";

/** Href verso la guida, opzionalmente a una sezione ancorata (es. "step-6"). */
export function guideHref(anchor?: string): string {
  return anchor ? `${GUIDA_PATH}#${anchor}` : GUIDA_PATH;
}

export type RecGuide = {
  /** Ancora della sezione nella pagina /guida-open-data. */
  anchor: string;
  /** Titolo leggibile della sezione (testo del link). */
  sezione: string;
  /** Consiglio sintetico su come colmare il gap. */
  consiglio: string;
};

/** Mappa il codice di una raccomandazione alla sezione della guida che lo risolve. */
export const REC_GUIDE: Record<string, RecGuide> = {
  no_open_data: {
    anchor: "step-1",
    sezione: "Avviare la policy: governance e atti",
    consiglio:
      "Parti dalla governance: nomina (o verifica) l'RTD, costituisci il gruppo di lavoro trasversale e approva la delibera di indirizzo open data.",
  },
  open_license: {
    anchor: "step-5",
    sezione: "Formati aperti e licenza",
    consiglio:
      "Adotta una licenza aperta unica — CC0 o CC BY 4.0 (obbligatorie per i dati di elevato valore) — e dichiarala nella delibera, applicandola a tutto il catalogo.",
  },
  open_format: {
    anchor: "step-5",
    sezione: "Formati aperti e licenza",
    consiglio:
      "Converti i dati in formati aperti e leggibili meccanicamente (CSV/JSON; GeoJSON, GML o Shapefile per i dati geografici), evitando il PDF.",
  },
  freshness: {
    anchor: "step-8",
    sezione: "Mantenere e aggiornare",
    consiglio:
      "Dichiara e rispetta una frequenza di aggiornamento per ogni dataset; dove i dati nascono da un gestionale, automatizza l'estrazione.",
  },
  dcat_ap_it: {
    anchor: "step-6",
    sezione: "Metadatare secondo DCAT-AP_IT",
    consiglio:
      "Compila i metadati secondo il profilo DCAT-AP_IT: è la condizione perché il dataset confluisca in dati.gov.it e nel portale europeo.",
  },
  hvd: {
    anchor: "step-3",
    sezione: "Scegliere i dataset prioritari",
    consiglio:
      "Dai priorità ai dati di elevato valore (HVD): geospaziali, mobilità (GTFS), statistici, ambiente — quelli a maggior impatto per un Comune.",
  },
  sector_gap: {
    anchor: "step-3",
    sezione: "Scegliere i dataset prioritari",
    consiglio:
      "Pianifica la pubblicazione partendo dai settori chiave mancanti per il ruolo dell'ente, in ordine di priorità: sono gli ambiti a maggior domanda di riuso.",
  },
  hvd_coverage: {
    anchor: "step-3",
    sezione: "Scegliere i dataset prioritari",
    consiglio:
      "Completa le categorie HVD ancora scoperte: sono i dati a maggior ritorno di riuso e impatto economico secondo il Reg. UE 2023/138.",
  },
};

export function recGuide(code: string): RecGuide | undefined {
  return REC_GUIDE[code];
}

/**
 * I gap di dato/domanda di riuso (testo libero: popolazione mancante, nessun
 * GTFS, ecc.) non hanno un codice: si colmano censendo e prioritizzando i
 * dataset, quindi rimandiamo alle sezioni 2-3 della guida.
 */
export const GAP_GUIDE: RecGuide = {
  anchor: "step-2",
  sezione: "Censire e prioritizzare i dataset",
  consiglio:
    "Questi gap si colmano aprendo i dataset richiesti: censisci il patrimonio informativo e seleziona la prima ondata secondo obbligo, valore e domanda reale.",
};
