"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { TerritorioExtra, type TerritorioExtraData } from "@/components/territorio/TerritorioExtra";
import { downloadSiteZip } from "@/lib/territorioSite";
import type { ModalitaProgramma, ProgrammaRequest, ProgrammaResponse } from "@/lib/types";
import { DashboardGate } from "@/components/DashboardGate";
import { DisclaimerBanner } from "@/components/territorio/DisclaimerBanner";
import { ProposalCard } from "@/components/territorio/ProposalCard";
import { SourcesList } from "@/components/territorio/SourcesList";
import { SwotGrid } from "@/components/territorio/SwotGrid";
import { ZoneSelector, type ZoneSelection } from "@/components/territorio/ZoneSelector";
import { downloadSchedaMarkdown } from "@/lib/programmaMarkdown";
import { downloadSchedaPdf } from "@/lib/programmaPdf";

/*
 * Studio del territorio — la UI del verticale PA (spec 05 + 06).
 *
 * Selezione del territorio: comune (autocomplete OSM→ISTAT) con mappa del
 * confine comunale. L'unità di analisi è l'intero comune; la strategia per le
 * città grandi (modalità macro: aggregati + top-N) è decisa dal backend.
 */

type Stato =
  | { fase: "idle" }
  | { fase: "loading" }
  | { fase: "errore"; messaggio: string }
  | { fase: "risultato"; scheda: ProgrammaResponse };

/** Un passaggio del feed di avanzamento (fonte o singola chiamata strumento). */
type Step = {
  key: string;
  label: string;
  kind: "fonte" | "tool";
  phase: "start" | "end" | "error";
};

const FONTE_LABEL: Record<string, string> = {
  ckan: "Cataloghi open data",
  istat: "ISTAT",
  eurostat: "Eurostat",
  oecd: "OCSE",
  opencoesione: "OpenCoesione",
  osm: "OpenStreetMap",
  ispra: "ISPRA",
  kg: "Analisi (memoria)",
  sintesi: "Sintesi del report",
};

const TOOL_LABEL: Record<string, string> = {
  opencoesione_resolve_territorio: "OpenCoesione · risoluzione territorio",
  opencoesione_search_projects: "OpenCoesione · ricerca progetti",
  opencoesione_get_project: "OpenCoesione · dettaglio progetto",
  opencoesione_funding_capacity: "OpenCoesione · capacità di spesa",
  opencoesione_territorial_aggregates: "OpenCoesione · aggregati territoriali",
  opencoesione_search_soggetti: "OpenCoesione · soggetti attuatori",
  opencoesione_query_local: "OpenCoesione · aggregati locali",
  opencoesione_reference_values: "OpenCoesione · valori di riferimento",
  ispra_risk_indicators: "ISPRA · indicatori di rischio",
  istat_list_dataflows: "ISTAT · catalogo dataset",
  istat_get_structure: "ISTAT · struttura dataset",
  istat_get_codelist: "ISTAT · codici",
  istat_get_data: "ISTAT · estrazione dati",
  geocode_address: "OpenStreetMap · geocoding",
  find_nearby_places: "OpenStreetMap · servizi vicini",
  explore_area: "OpenStreetMap · esplorazione area",
  get_route: "OpenStreetMap · calcolo percorso",
  osm_lookup_comune: "OpenStreetMap · ricerca comune",
  osm_list_zones: "OpenStreetMap · zone riconosciute",
  osm_get_zone: "OpenStreetMap · geometria zona",
  kg_query: "Memoria analisi · interrogazione",
};

function toolLabel(name: string): string {
  return TOOL_LABEL[name] ?? name.replaceAll("_", " ");
}

function formatGeneratoIl(iso: string): string {
  try {
    return new Date(iso).toLocaleString("it-IT", { dateStyle: "long", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function TerritorioInner() {
  const { getToken } = useAuth();
  const [selection, setSelection] = useState<ZoneSelection | null>(null);
  const [codManuale, setCodManuale] = useState("");
  const [tema, setTema] = useState("");
  const [stato, setStato] = useState<Stato>({ fase: "idle" });
  const [attesaSec, setAttesaSec] = useState(0);
  const [steps, setSteps] = useState<Step[]>([]);
  const [extra, setExtra] = useState<TerritorioExtraData>({});
  const [esportandoSito, setEsportandoSito] = useState(false);

  // Timer di attesa: /programma non ha (ancora) eventi di progresso e con un
  // LLM locale il fan-out può durare minuti — il contatore mostra che è vivo.
  useEffect(() => {
    if (stato.fase !== "loading") {
      setAttesaSec(0);
      return;
    }
    const t = setInterval(() => setAttesaSec((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [stato.fase]);

  const codComune = (codManuale.trim() || selection?.cod_comune) ?? "";

  // Un solo messaggio di stato per la barra di avanzamento: l'attività in corso
  // (ultimo step ancora "start"), con fallback all'ultimo step noto.
  const statusLabel =
    [...steps].reverse().find((s) => s.phase === "start")?.label ??
    steps[steps.length - 1]?.label ??
    "Preparazione dell'analisi…";

  function pushStep(step: Step) {
    setSteps((prev) => {
      // L'evento "end/error" aggiorna lo step aperto con la stessa chiave.
      const idx = [...prev].reverse().findIndex(
        (s) => s.key === step.key && s.phase === "start",
      );
      if (step.phase !== "start" && idx !== -1) {
        const real = prev.length - 1 - idx;
        const next = [...prev];
        next[real] = { ...next[real], phase: step.phase };
        return next;
      }
      return [...prev, step];
    });
  }

  async function genera(e: React.FormEvent) {
    e.preventDefault();
    await run(false);
  }

  async function run(force: boolean) {
    const cod = codComune.trim();
    if (!cod) return;
    setStato({ fase: "loading" });
    setSteps([]);
    try {
      const body: ProgrammaRequest = {
        cod_comune: cod,
        comune_nome: selection?.comune_nome ?? null,
        // Analisi a livello di INTERO comune: niente zona (la popolazione e la
        // strategia macro per le città grandi le decide il backend).
        tema: tema.trim() || null,
        // Analisi UNICA: un fan-out → sintesi + SWOT + proposte + idee +
        // spunti di marketing territoriale (questi ultimi se la fonte web è
        // attiva lato backend). Niente più "tipo di analisi".
        modalita: "completa" satisfies ModalitaProgramma,
        // "Rigenera": salta la cache lato backend e rifà il fan-out.
        ...(force ? { force_refresh: true } : {}),
      };
      const token = await getToken();
      const res = await apiFetch("/programma/stream", {
        method: "POST",
        token,
        body: JSON.stringify(body),
      });
      if (!res.ok || !res.body) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}${detail ? ` — ${detail.slice(0, 200)}` : ""}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let scheda: ProgrammaResponse | null = null;
      let streamError: string | null = null;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let nl: number;
        while ((nl = buffer.indexOf("\n")) !== -1) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          let ev: Record<string, unknown>;
          try {
            ev = JSON.parse(line);
          } catch {
            continue;
          }
          if (ev.event === "status") {
            const source = String(ev.source ?? "");
            pushStep({
              key: `fonte:${source}`,
              label: FONTE_LABEL[source] ?? source,
              kind: "fonte",
              phase: ev.error ? "error" : (ev.phase as "start" | "end"),
            });
          } else if (ev.event === "tool" && ev.name) {
            const name = String(ev.name);
            pushStep({
              key: `tool:${name}`,
              label: toolLabel(name),
              kind: "tool",
              phase: (ev.phase as "start" | "end" | "error") ?? "start",
            });
          } else if (ev.event === "result") {
            scheda = ev.scheda as ProgrammaResponse;
          } else if (ev.event === "error") {
            streamError = String(ev.message ?? "errore sconosciuto");
          }
        }
      }
      if (streamError) throw new Error(streamError);
      if (!scheda) throw new Error("Lo stream si è chiuso senza un risultato.");
      setStato({ fase: "risultato", scheda });
    } catch (err) {
      setStato({
        fase: "errore",
        messaggio: err instanceof Error ? err.message : String(err),
      });
    }
  }

  const scheda = stato.fase === "risultato" ? stato.scheda : null;

  // Export "sito completo": recupera (best-effort) il confine del comune per la
  // mappa e impacchetta tutto in uno ZIP statico, responsive e self-contained.
  async function esportaSito() {
    if (!scheda) return;
    setEsportandoSito(true);
    try {
      let confine: GeoJSON.Feature | null = null;
      const osmId = selection?.osm_id;
      if (osmId && codComune) {
        try {
          const token = await getToken();
          const params = new URLSearchParams({ osm_id: osmId, cod_comune: codComune });
          const res = await apiFetch(`/territorio/confine?${params}`, { token });
          if (res.ok) confine = ((await res.json()) as { feature: GeoJSON.Feature }).feature ?? null;
        } catch {
          /* la mappa è un di più: il sito si genera comunque */
        }
      }
      await downloadSiteZip(scheda, extra, confine);
    } finally {
      setEsportandoSito(false);
    }
  }

  // Nel report unico le idee si riconoscono dal generatore; gli spunti di
  // marketing dalla lente (o dai generatori di marketing).
  const MARKETING_GEN = new Set([
    "caso_analogo",
    "asset_sottoutilizzato",
    "domanda_emergente",
  ]);
  const isMarketingP = (p: { generatore?: string | null; lente?: string | null }) =>
    !!p.lente || (!!p.generatore && MARKETING_GEN.has(p.generatore));
  const proposte = scheda?.proposte.filter((p) => !p.generatore && !p.lente) ?? [];
  const marketing = scheda?.proposte.filter(isMarketingP) ?? [];
  const idee = scheda?.proposte.filter((p) => !!p.generatore && !isMarketingP(p)) ?? [];
  const lenti = Array.from(new Set(marketing.map((p) => (p.lente as string) || "altro")));
  const LENTE_TITLE: Record<string, string> = {
    turismo_cultura: "Turismo & cultura",
    viabilita_mobilita: "Viabilità & mobilità",
    sicurezza_vivibilita: "Sicurezza & vivibilità",
    attrattivita_brand: "Attrattività & brand",
    altro: "Altri spunti",
  };

  return (
    <main className="container py-4" style={{ maxWidth: 960 }}>
      {/* ── Header di selezione: comune + mappa del confine comunale ── */}
      <div className="no-print">
        <h1 className="h3 mb-1">Studio del territorio</h1>
        <p className="text-muted mb-4">
          Analisi completa evidence-based per un comune: quadro di sintesi,
          SWOT, proposte concrete e idee nuove dai confronti con territori
          simili — ogni affermazione ancorata a fonti pubbliche verificabili.
          Non è materiale elettorale.
        </p>

        <form className="card shadow-sm mb-4" onSubmit={genera} aria-busy={stato.fase === "loading"}>
          <div className="card-body">
            <ZoneSelector onChange={setSelection} />

            <div className="row g-3 mt-1">
              <div className="col-12 col-md-5">
                <label htmlFor="tema" className="form-label fw-semibold">
                  Tema <span className="fw-normal text-muted">(opzionale)</span>
                </label>
                <input
                  id="tema"
                  className="form-control"
                  value={tema}
                  onChange={(e) => setTema(e.target.value)}
                  placeholder="es. energia, trasporti"
                />
                <div className="form-text">
                  Per le città grandi, indicare un tema rende l&apos;analisi più
                  mirata (altrimenti si concentra sui temi a maggiore dotazione).
                </div>
              </div>
            </div>

            <details className="mt-2">
              <summary className="small text-muted" style={{ cursor: "pointer" }}>
                Conosci già il codice ISTAT? Inseriscilo direttamente
              </summary>
              <div className="mt-2" style={{ maxWidth: 260 }}>
                <label htmlFor="cod-comune" className="form-label fw-semibold">
                  Codice ISTAT
                </label>
                <input
                  id="cod-comune"
                  className="form-control"
                  value={codManuale}
                  onChange={(e) => setCodManuale(e.target.value)}
                  placeholder="es. 110002 (Barletta)"
                  pattern="\d{6}"
                  title="6 cifre, es. 072006 per Bari"
                  inputMode="numeric"
                />
              </div>
            </details>

            <div className="mt-3 d-flex align-items-center gap-3">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={stato.fase === "loading" || !codComune}
              >
                {stato.fase === "loading" ? "Analisi in corso…" : "Genera analisi"}
              </button>
              {stato.fase !== "loading" && !codComune ? (
                <span className="small text-muted">
                  Seleziona un comune per generare la scheda.
                </span>
              ) : null}
            </div>

            {stato.fase === "loading" ? (
              <div className="mt-3" role="status" aria-label="Avanzamento dell'analisi">
                <div className="progress" style={{ height: "0.5rem" }}>
                  <div
                    className="progress-bar progress-bar-striped progress-bar-animated"
                    role="progressbar"
                    aria-valuetext={statusLabel}
                    style={{ width: "100%" }}
                  />
                </div>
                <div className="small text-muted mt-2 d-flex align-items-center justify-content-between gap-2">
                  <span className="text-truncate">{statusLabel}</span>
                  <span className="flex-shrink-0 font-monospace">{attesaSec}s</span>
                </div>
              </div>
            ) : null}
          </div>
        </form>

        {stato.fase === "errore" ? (
          <div className="alert alert-danger" role="alert">
            <strong>Generazione fallita.</strong> {stato.messaggio}
          </div>
        ) : null}
      </div>

      {/* ── Risultato (qui arriverà il toggle Scheda | Idee, Pezzo 8) ── */}
      {scheda ? (
        <div id="scheda-programma">
          <div className="d-flex align-items-start justify-content-between gap-2 mb-3">
            <div>
              <h2 className="h4 mb-0">
                Analisi del territorio — comune {scheda.comune}
                {scheda.zona ? ` · ${scheda.zona}` : ""}
              </h2>
              <p className="small text-muted mb-0">
                Generata il {formatGeneratoIl(scheda.generato_il)}
              </p>
            </div>
            <div className="d-flex gap-2 no-print">
              {scheda.da_cache ? (
                <button
                  type="button"
                  className="btn btn-outline-secondary btn-sm"
                  onClick={() => run(true)}
                  title="Rigenera l'analisi ignorando la cache"
                >
                  Rigenera
                </button>
              ) : null}
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => downloadSchedaPdf(scheda)}
              >
                Esporta PDF
              </button>
              <button
                type="button"
                className="btn btn-outline-primary btn-sm"
                onClick={() => downloadSchedaMarkdown(scheda)}
              >
                Esporta Markdown
              </button>
              <button
                type="button"
                className="btn btn-success btn-sm"
                onClick={esportaSito}
                disabled={esportandoSito}
                title="Scarica un sito statico, responsive e condivisibile con tutta l'analisi"
              >
                {esportandoSito ? "Generazione…" : "Esporta come sito"}
              </button>
            </div>
          </div>

          {scheda.da_cache ? (
            <div className="alert alert-light border d-flex align-items-center gap-2 py-2 small no-print" role="status">
              <span aria-hidden="true">💾</span>
              <span>
                Analisi servita dalla <strong>cache</strong> (generata il{" "}
                {formatGeneratoIl(scheda.generato_il)}). Premi <em>Rigenera</em> per
                rifarla con i dati più recenti.
              </span>
            </div>
          ) : null}

          <DisclaimerBanner text={scheda.disclaimer} />

          {scheda.sintesi?.trim() ? (
            <section className="mb-4" aria-label="Quadro di sintesi">
              <h2 className="h5 mb-2">Quadro di sintesi</h2>
              <p className="mb-0" style={{ whiteSpace: "pre-line" }}>
                {scheda.sintesi}
              </p>
            </section>
          ) : null}

          {Object.values(scheda.swot).some((v) => v.length > 0) ? (
            <>
              <h2 className="h5 mb-3">Analisi SWOT</h2>
              <SwotGrid swot={scheda.swot} />
            </>
          ) : null}

          <h2 className="h5 mt-4 mb-3">Proposte</h2>
          {proposte.length === 0 ? (
            <p className="text-muted">
              Nessuna proposta ha superato la verifica delle fonti per questa
              richiesta. Prova ad allargare o a cambiare il tema.
            </p>
          ) : (
            <div className="d-flex flex-column gap-3">
              {proposte.map((p, i) => (
                <ProposalCard key={i} proposta={p} />
              ))}
            </div>
          )}

          {idee.length > 0 ? (
            <>
              <h2 className="h5 mt-4 mb-3">Idee per il territorio</h2>
              {scheda.idee_sintesi?.trim() ? (
                <p className="mb-2" style={{ whiteSpace: "pre-line" }}>
                  {scheda.idee_sintesi}
                </p>
              ) : null}
              <p className="small text-muted">
                Spunti nuovi generati dagli scarti tra dati e attuato: confronti con
                comuni simili, bisogni scoperti, progetti fermi, risorse disponibili.
                Elencate dalla più promettente.
              </p>
              <div className="d-flex flex-column gap-3">
                {idee.map((p, i) => (
                  <ProposalCard key={i} proposta={p} />
                ))}
              </div>
            </>
          ) : null}

          {marketing.length > 0 ? (
            <>
              <h2 className="h5 mt-4 mb-3">Marketing territoriale — spunti di attrattività</h2>
              <p className="small text-muted">
                Spunti di posizionamento ispirati a iniziative di altri enti: ogni
                spunto cita una premessa locale e un precedente esterno. Non sono atti
                amministrativi né progetti finanziati.
              </p>
              <div className="d-flex flex-column gap-4">
                {lenti.map((lente) => (
                  <div key={lente}>
                    <h3 className="h6 fw-bold mb-2">{LENTE_TITLE[lente] ?? lente}</h3>
                    <div className="d-flex flex-column gap-3">
                      {marketing
                        .filter((p) => ((p.lente as string) || "altro") === lente)
                        .map((p, i) => (
                          <ProposalCard key={i} proposta={p} />
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : null}

          <SourcesList citazioni={scheda.citazioni} />

          {/* F2 — analisi unica: maturità + valore + report dello stesso comune */}
          <TerritorioExtra
            codComune={codComune}
            comuneNome={selection?.comune_nome ?? null}
            scheda={scheda}
            onData={setExtra}
          />
        </div>
      ) : null}
    </main>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <TerritorioInner />
    </DashboardGate>
  );
}
