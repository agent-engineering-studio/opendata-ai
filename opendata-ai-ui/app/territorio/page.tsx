"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import type { ModalitaProgramma, ProgrammaRequest, ProgrammaResponse } from "@/lib/types";
import { DashboardGate } from "@/components/DashboardGate";
import { DisclaimerBanner } from "@/components/territorio/DisclaimerBanner";
import { ProposalCard } from "@/components/territorio/ProposalCard";
import { SourcesList } from "@/components/territorio/SourcesList";
import { SwotGrid } from "@/components/territorio/SwotGrid";
import { ZoneSelector, type ZoneSelection } from "@/components/territorio/ZoneSelector";

/*
 * Studio del territorio — la UI del verticale PA (spec 05 + 06).
 *
 * Selezione del territorio: comune (autocomplete OSM→ISTAT) → tipo zona →
 * zona riconosciuta OSM (niente disegno a mano libera). L'area risultati
 * ospiterà il toggle Scheda | Idee (Pezzo 8).
 */

type Stato =
  | { fase: "idle" }
  | { fase: "loading" }
  | { fase: "errore"; messaggio: string }
  | { fase: "risultato"; scheda: ProgrammaResponse };

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
  const [zona, setZona] = useState("");
  const [tema, setTema] = useState("");
  const [modalita, setModalita] = useState<ModalitaProgramma>("scheda");
  // Cache per modalità: il toggle Scheda|Idee non ributta via il lavoro fatto.
  const [risultati, setRisultati] = useState<
    Partial<Record<ModalitaProgramma, ProgrammaResponse>>
  >({});
  const [stato, setStato] = useState<Stato>({ fase: "idle" });
  const [attesaSec, setAttesaSec] = useState(0);

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

  async function genera(e: React.FormEvent) {
    e.preventDefault();
    const cod = codComune.trim();
    if (!cod) return;
    setStato({ fase: "loading" });
    try {
      const body: ProgrammaRequest = {
        cod_comune: cod,
        comune_nome: selection?.comune_nome ?? null,
        // La zona OSM selezionata vince sul testo libero (che resta il fallback).
        zona: selection?.zona_label ?? (zona.trim() || null),
        zona_tipo: selection?.zona_tipo ?? null,
        zona_osm_id: selection?.zona_osm_id ?? null,
        tema: tema.trim() || null,
        modalita,
      };
      const token = await getToken();
      const res = await apiFetch("/programma", {
        method: "POST",
        token,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}${detail ? ` — ${detail.slice(0, 200)}` : ""}`);
      }
      const scheda = (await res.json()) as ProgrammaResponse;
      setRisultati((prev) => ({ ...prev, [modalita]: scheda }));
      setStato({ fase: "risultato", scheda });
    } catch (err) {
      setStato({
        fase: "errore",
        messaggio: err instanceof Error ? err.message : String(err),
      });
    }
  }

  function cambiaModalita(m: ModalitaProgramma) {
    setModalita(m);
    const cached = risultati[m];
    setStato(cached ? { fase: "risultato", scheda: cached } : { fase: "idle" });
  }

  const scheda = stato.fase === "risultato" ? stato.scheda : null;
  const isIdee = modalita === "idee";

  return (
    <main className="container py-4" style={{ maxWidth: 960 }}>
      {/* ── Header di selezione (qui arriverà il selettore zona OSM, Pezzo 6) ── */}
      <div className="no-print">
        <h1 className="h3 mb-1">Studio del territorio</h1>
        <p className="text-muted mb-4">
          Scheda programmatica evidence-based per un comune: analisi SWOT e
          proposte concrete, ogni affermazione ancorata a fonti pubbliche
          verificabili. Non è materiale elettorale.
        </p>

        <form className="card shadow-sm mb-4" onSubmit={genera} aria-busy={stato.fase === "loading"}>
          <div className="card-body">
            <ZoneSelector onChange={setSelection} />

            <div className="row g-3 mt-1">
              {!selection?.zona_osm_id ? (
                <div className="col-12 col-md-4">
                  <label htmlFor="zona" className="form-label fw-semibold">
                    Descrizione zona{" "}
                    <span className="fw-normal text-muted">(opzionale)</span>
                  </label>
                  <input
                    id="zona"
                    className="form-control"
                    value={zona}
                    onChange={(e) => setZona(e.target.value)}
                    placeholder="es. area industriale"
                  />
                </div>
              ) : null}
              <div className="col-12 col-md-4">
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

            <fieldset className="mt-3">
              <legend className="form-label fw-semibold fs-6 mb-1">Modalità</legend>
              <div className="btn-group" role="group" aria-label="Modalità di analisi">
                <button
                  type="button"
                  className={`btn btn-sm ${!isIdee ? "btn-primary" : "btn-outline-primary"}`}
                  aria-pressed={!isIdee}
                  onClick={() => cambiaModalita("scheda")}
                >
                  Scheda
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${isIdee ? "btn-primary" : "btn-outline-primary"}`}
                  aria-pressed={isIdee}
                  onClick={() => cambiaModalita("idee")}
                >
                  Idee
                </button>
              </div>
              <p className="form-text mb-0">
                {isIdee
                  ? "Brainstorming evidence-based: idee nuove per il territorio dai confronti con comuni simili, bisogni scoperti, progetti fermi e risorse disponibili."
                  : "Fotografia SWOT del territorio con proposte ancorate alle fonti."}
              </p>
            </fieldset>

            <div className="mt-3 d-flex align-items-center gap-3">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={stato.fase === "loading" || !codComune}
              >
                {stato.fase === "loading"
                  ? "Generazione in corso…"
                  : isIdee
                    ? "Genera idee"
                    : "Genera scheda"}
              </button>
              {stato.fase === "loading" ? (
                <span className="small text-muted" role="status">
                  Interrogo le fonti (ISTAT, OpenCoesione…) e sintetizzo la
                  scheda — {attesaSec}s. Con un modello locale (Ollama) possono
                  servire diversi minuti: gli agenti si serializzano sulla GPU.
                </span>
              ) : !codComune ? (
                <span className="small text-muted">
                  Seleziona un comune per generare la scheda.
                </span>
              ) : null}
            </div>
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
                {isIdee ? "Idee per il territorio" : "Scheda"} — comune {scheda.comune}
                {scheda.zona ? ` · ${scheda.zona}` : ""}
              </h2>
              <p className="small text-muted mb-0">
                Generata il {formatGeneratoIl(scheda.generato_il)}
              </p>
            </div>
            <button
              type="button"
              className="btn btn-outline-primary btn-sm no-print"
              onClick={() => window.print()}
            >
              Esporta PDF
            </button>
          </div>

          <DisclaimerBanner text={scheda.disclaimer} />

          {/* In modalità idee la SWOT è facoltativa: mostrata solo se non vuota. */}
          {Object.values(scheda.swot).some((v) => v.length > 0) ? (
            <>
              <h2 className="h5 mb-3">Analisi SWOT</h2>
              <SwotGrid swot={scheda.swot} />
            </>
          ) : null}

          <h2 className="h5 mt-4 mb-3">{isIdee ? "Idee" : "Proposte"}</h2>
          {scheda.proposte.length === 0 ? (
            <p className="text-muted">
              {isIdee
                ? "Nessuna idea ha superato la verifica delle premesse. Il generatore comparativo richiede il mirror locale e l'anagrafica comuni (make oc-sync + make comuni-sync)."
                : "Nessuna proposta ha superato la verifica delle fonti per questa richiesta. Prova ad allargare il tema o a omettere la zona."}
            </p>
          ) : (
            <div className="d-flex flex-column gap-3">
              {scheda.proposte.map((p, i) => (
                <ProposalCard key={i} proposta={p} />
              ))}
            </div>
          )}

          <SourcesList citazioni={scheda.citazioni} />
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
