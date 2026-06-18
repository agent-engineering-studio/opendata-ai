"use client";

/*
 * Sezioni aggiuntive dell'analisi unica di Territorio (F2): oltre al /programma,
 * mostra anche Scorecard di maturità, Report Comune e portafoglio di Valore per lo
 * stesso comune. Orchestrazione frontend best-effort degli endpoint esistenti:
 * ogni sezione è indipendente e degrada con grazia (una fonte giù non blocca le altre).
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import type { Guida } from "@/lib/scorecardPdf";
import { downloadSiteZip } from "@/lib/territorioSite";
import type { ProgrammaResponse } from "@/lib/types";

type Scorecard = {
  entity: { id: number; name: string };
  level: string;
  overall: number;
  dimensions: { policy: number; portal: number; quality: number; impact: number };
  n_datasets: number | null;
  insufficient_data?: boolean;
  guida?: Guida | null;
};

type Report = {
  place?: { name?: string };
  narrativa?: string;
  sezioni?: {
    investimenti?: {
      n_progetti?: number;
      finanziamento_totale?: number;
      per_tema?: { tema: string; finanziamento: number }[];
    };
    gap_dato?: string[];
  };
};

type Portfolio = {
  count: number;
  pct_hvd: number | null;
  pct_open_license: number | null;
  avg_freshness_days: number | null;
  avg_stars: number | null;
  avg_reuse: number | null;
};

type Loadable<T> = { stato: "loading" | "ok" | "ko"; dato?: T; err?: string };

const LEVEL_COLOR: Record<string, string> = {
  Beginner: "#dc2626",
  Follower: "#d97706",
  "Fast-tracker": "#2563eb",
  "Trend-setter": "#059669",
};

function eur(n?: number | null): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 }).format(n) + " €";
}
function pct(n?: number | null): string {
  return n == null ? "—" : `${Math.round(n)}%`;
}

export function TerritorioExtra({
  codComune,
  comuneNome,
  scheda,
}: {
  codComune: string;
  comuneNome?: string | null;
  scheda: ProgrammaResponse;
}) {
  const { getToken } = useAuth();
  const [sc, setSc] = useState<Loadable<Scorecard>>({ stato: "loading" });
  const [rep, setRep] = useState<Loadable<Report>>({ stato: "loading" });
  const [val, setVal] = useState<Loadable<Portfolio>>({ stato: "loading" });

  useEffect(() => {
    let alive = true;
    const cod = codComune.trim();
    if (!cod) return;
    setSc({ stato: "loading" });
    setRep({ stato: "loading" });
    setVal({ stato: "loading" });

    (async () => {
      const token = await getToken();

      // Report Comune (parallelo, indipendente)
      apiFetch("/territory/report", {
        method: "POST",
        token,
        body: JSON.stringify({ istat_code: cod }),
      })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((d: Report) => alive && setRep({ stato: "ok", dato: d }))
        .catch((e) => alive && setRep({ stato: "ko", err: String(e?.message ?? e) }));

      // Scorecard maturità → poi Valore (portfolio legato all'entity_id)
      try {
        const r = await apiFetch("/maturity/assess", {
          method: "POST",
          token,
          body: JSON.stringify({
            entity: comuneNome || cod,
            comune_nome: comuneNome ?? undefined,
            istat_code: cod,
          }),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const scorecard = (await r.json()) as Scorecard;
        if (alive) setSc({ stato: "ok", dato: scorecard });

        const eid = scorecard?.entity?.id;
        if (eid) {
          const rv = await apiFetch(`/value/portfolio?entity_id=${eid}`, { token });
          if (!rv.ok) throw new Error(`HTTP ${rv.status}`);
          const p = (await rv.json()) as Portfolio;
          if (alive) setVal({ stato: "ok", dato: p });
        } else if (alive) {
          setVal({ stato: "ko", err: "nessun ente" });
        }
      } catch (e) {
        if (alive) {
          setSc((s) => (s.stato === "loading" ? { stato: "ko", err: String((e as Error)?.message ?? e) } : s));
          setVal((v) => (v.stato === "loading" ? { stato: "ko", err: "assessment fallito" } : v));
        }
      }
    })();

    return () => {
      alive = false;
    };
  }, [codComune, comuneNome, getToken]);

  return (
    <div className="d-flex flex-column gap-4 mt-4">
      <hr className="my-0" />
      <div className="d-flex flex-wrap justify-content-between align-items-start gap-2">
        <h2 className="h4 mb-0">Maturità, valore e profilo del comune</h2>
        <button
          type="button"
          className="btn btn-success btn-sm no-print"
          onClick={() =>
            downloadSiteZip(scheda, {
              scorecard: sc.dato,
              report: rep.dato,
              portfolio: val.dato,
            })
          }
          title="Scarica un sito statico condivisibile con tutta l'analisi"
        >
          Esporta sito completo (ZIP)
        </button>
      </div>
      <p className="text-muted mb-0" style={{ fontSize: 14 }}>
        Le altre letture sullo stesso comune: maturità degli open data, valore del
        patrimonio e profilo territoriale. Sezioni indipendenti dall&apos;analisi
        principale.
      </p>

      {/* ── Scorecard maturità ── */}
      <section className="card shadow-sm">
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-center mb-2">
            <h3 className="h6 mb-0">Maturità open data</h3>
            <Link href={`/scorecard?entity=${encodeURIComponent(comuneNome || codComune)}&istat=${codComune}`}
              className="small">Scorecard completa →</Link>
          </div>
          {sc.stato === "loading" ? (
            <p className="text-muted small mb-0">Valutazione in corso…</p>
          ) : sc.stato === "ko" ? (
            <p className="text-muted small mb-0">Non disponibile ({sc.err}).</p>
          ) : sc.dato?.insufficient_data && sc.dato.guida ? (
            <div>
              <span className="badge bg-warning text-dark mb-2">Dato insufficiente</span>
              <p className="mb-1" style={{ fontSize: 14 }}>{sc.dato.guida.premessa}</p>
              <Link href={`/scorecard?entity=${encodeURIComponent(comuneNome || codComune)}&istat=${codComune}`}
                className="small fw-semibold">Apri la guida operativa open-data →</Link>
            </div>
          ) : (
            <div className="d-flex flex-wrap align-items-center gap-3">
              <span className="badge rounded-pill px-3 py-2"
                style={{ backgroundColor: LEVEL_COLOR[sc.dato!.level] ?? "#334155", color: "white" }}>
                {sc.dato!.level} · {Math.round(sc.dato!.overall)}/100
              </span>
              <span className="small text-muted">
                Policy {Math.round(sc.dato!.dimensions.policy)} · Portale {Math.round(sc.dato!.dimensions.portal)} ·
                Qualità {Math.round(sc.dato!.dimensions.quality)} · Impatto {Math.round(sc.dato!.dimensions.impact)}
                {sc.dato!.n_datasets != null ? ` · ${sc.dato!.n_datasets} dataset` : ""}
              </span>
            </div>
          )}
        </div>
      </section>

      {/* ── Valore del patrimonio ── */}
      <section className="card shadow-sm">
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-center mb-2">
            <h3 className="h6 mb-0">Valore del patrimonio dati</h3>
            <Link href="/valore" className="small">Dettaglio valore →</Link>
          </div>
          {val.stato === "loading" ? (
            <p className="text-muted small mb-0">Calcolo in corso…</p>
          ) : val.stato === "ko" || !val.dato?.count ? (
            <p className="text-muted small mb-0">
              Nessun dataset valutato per questo comune (esegui prima l&apos;assessment di maturità).
            </p>
          ) : (
            <div className="row g-3 text-center">
              <Kpi label="Dataset" value={String(val.dato.count)} />
              <Kpi label="HVD" value={pct(val.dato.pct_hvd)} />
              <Kpi label="Licenza aperta" value={pct(val.dato.pct_open_license)} />
              <Kpi label="Stelle medie" value={val.dato.avg_stars != null ? val.dato.avg_stars.toFixed(1) : "—"} />
              <Kpi label="Riuso" value={val.dato.avg_reuse != null ? val.dato.avg_reuse.toFixed(1) : "—"} />
            </div>
          )}
        </div>
      </section>

      {/* ── Report comune (profilo + investimenti + gap) ── */}
      <section className="card shadow-sm">
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-center mb-2">
            <h3 className="h6 mb-0">Profilo e investimenti del comune</h3>
            <Link href={`/territorio-report?istat=${codComune}`} className="small">Report completo →</Link>
          </div>
          {rep.stato === "loading" ? (
            <p className="text-muted small mb-0">Costruzione del report…</p>
          ) : rep.stato === "ko" ? (
            <p className="text-muted small mb-0">Non disponibile ({rep.err}).</p>
          ) : (
            <div className="d-flex flex-column gap-2">
              {rep.dato?.narrativa ? (
                <p className="mb-1" style={{ fontSize: 14 }}>{rep.dato.narrativa}</p>
              ) : null}
              <div className="small">
                <strong>Investimenti pubblici (OpenCoesione):</strong>{" "}
                {rep.dato?.sezioni?.investimenti?.n_progetti ?? 0} progetti ·{" "}
                {eur(rep.dato?.sezioni?.investimenti?.finanziamento_totale)} finanziati
              </div>
              {rep.dato?.sezioni?.gap_dato?.length ? (
                <div className="small text-muted">
                  <strong>Gap di dato:</strong> {rep.dato.sezioni.gap_dato.join(" · ")}
                </div>
              ) : null}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="col">
      <div className="h5 mb-0 text-primary">{value}</div>
      <div className="small text-muted">{label}</div>
    </div>
  );
}
