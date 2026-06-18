"use client";

/*
 * Sezioni aggiuntive dell'analisi unica di Territorio: oltre al /programma, mostra
 * anche Maturità open data, Valore del patrimonio e Profilo/Investimenti dello stesso
 * comune. Orchestrazione frontend best-effort degli endpoint esistenti: ogni sezione è
 * indipendente e degrada con grazia. I dati sono mostrati per intero e formattati
 * (niente link di richiamo). I risultati vengono risollevati al genitore (onData) per
 * l'export "sito completo".
 */

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import type { Guida } from "@/lib/scorecardPdf";
import type { ProgrammaResponse } from "@/lib/types";

export type Scorecard = {
  entity: { id: number; name: string };
  level: string;
  overall: number;
  dimensions: { policy: number; portal: number; quality: number; impact: number };
  n_datasets: number | null;
  insufficient_data?: boolean;
  guida?: Guida | null;
};

export type Report = {
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

export type Portfolio = {
  count: number;
  pct_hvd: number | null;
  pct_open_license: number | null;
  avg_freshness_days: number | null;
  avg_stars: number | null;
  avg_reuse: number | null;
};

export type TerritorioExtraData = {
  scorecard?: Scorecard;
  report?: Report;
  portfolio?: Portfolio;
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
  onData,
}: {
  codComune: string;
  comuneNome?: string | null;
  scheda: ProgrammaResponse;
  onData?: (d: TerritorioExtraData) => void;
}) {
  const { getToken } = useAuth();
  const [sc, setSc] = useState<Loadable<Scorecard>>({ stato: "loading" });
  const [rep, setRep] = useState<Loadable<Report>>({ stato: "loading" });
  const [val, setVal] = useState<Loadable<Portfolio>>({ stato: "loading" });

  // Risolleva al genitore l'ultimo snapshot dei dati (per l'export "sito completo").
  const onDataRef = useRef(onData);
  onDataRef.current = onData;
  useEffect(() => {
    onDataRef.current?.({ scorecard: sc.dato, report: rep.dato, portfolio: val.dato });
  }, [sc.dato, rep.dato, val.dato]);

  useEffect(() => {
    let alive = true;
    const cod = codComune.trim();
    if (!cod) return;
    setSc({ stato: "loading" });
    setRep({ stato: "loading" });
    setVal({ stato: "loading" });

    (async () => {
      const token = await getToken();

      apiFetch("/territory/report", {
        method: "POST",
        token,
        body: JSON.stringify({ istat_code: cod }),
      })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((d: Report) => alive && setRep({ stato: "ok", dato: d }))
        .catch((e) => alive && setRep({ stato: "ko", err: String(e?.message ?? e) }));

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
        if (eid && !scorecard.insufficient_data) {
          const rv = await apiFetch(`/value/portfolio?entity_id=${eid}`, { token });
          if (!rv.ok) throw new Error(`HTTP ${rv.status}`);
          const p = (await rv.json()) as Portfolio;
          if (alive) setVal({ stato: "ok", dato: p });
        } else if (alive) {
          setVal({ stato: "ok", dato: { count: 0, pct_hvd: null, pct_open_license: null, avg_freshness_days: null, avg_stars: null, avg_reuse: null } });
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
      <div>
        <h2 className="h4 mb-1">Maturità, valore e profilo del comune</h2>
        <p className="text-muted mb-0" style={{ fontSize: 14 }}>
          Le altre letture sullo stesso comune. Sezioni indipendenti dall&apos;analisi principale.
        </p>
      </div>

      {/* ── Maturità open data ── */}
      <section className="card shadow-sm">
        <div className="card-body">
          <h3 className="h6 mb-2">Maturità open data</h3>
          {sc.stato === "loading" ? (
            <p className="text-muted small mb-0">Valutazione in corso…</p>
          ) : sc.stato === "ko" ? (
            <p className="text-muted small mb-0">Non disponibile ({sc.err}).</p>
          ) : sc.dato?.insufficient_data && sc.dato.guida ? (
            <div>
              <span className="badge bg-warning text-dark mb-2">Dato insufficiente</span>
              <p className="mb-2" style={{ fontSize: 14 }}>{sc.dato.guida.premessa}</p>
              <ol className="d-flex flex-column gap-2 mb-0" style={{ fontSize: 14, paddingLeft: 18 }}>
                {sc.dato.guida.passi.map((p, i) => (
                  <li key={i}>
                    <strong>{p.titolo}</strong>
                    <div className="text-muted" style={{ fontSize: 13 }}>{p.descrizione}</div>
                  </li>
                ))}
              </ol>
            </div>
          ) : (
            <div className="d-flex flex-wrap align-items-center gap-3">
              <span
                className="badge rounded-pill px-3 py-2"
                style={{ backgroundColor: LEVEL_COLOR[sc.dato!.level] ?? "#334155", color: "white" }}
              >
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
          <h3 className="h6 mb-2">Valore del patrimonio dati</h3>
          {val.stato === "loading" ? (
            <p className="text-muted small mb-0">Calcolo in corso…</p>
          ) : !val.dato?.count ? (
            <p className="text-muted small mb-0">
              Nessun dataset aperto valutato per questo comune: il valore si misura quando l&apos;ente
              pubblica i propri open data.
            </p>
          ) : (
            <div className="row g-3 text-center">
              <Kpi label="Dataset" value={String(val.dato.count)} />
              <Kpi label="Alto valore (HVD)" value={pct(val.dato.pct_hvd)} />
              <Kpi label="Licenza aperta" value={pct(val.dato.pct_open_license)} />
              <Kpi label="Stelle medie" value={val.dato.avg_stars != null ? val.dato.avg_stars.toFixed(1) : "—"} />
              <Kpi label="Riuso" value={val.dato.avg_reuse != null ? val.dato.avg_reuse.toFixed(1) : "—"} />
            </div>
          )}
        </div>
      </section>

      {/* ── Profilo e investimenti del comune ── */}
      <section className="card shadow-sm">
        <div className="card-body">
          <h3 className="h6 mb-2">Profilo e investimenti del comune</h3>
          {rep.stato === "loading" ? (
            <p className="text-muted small mb-0">Costruzione del report…</p>
          ) : rep.stato === "ko" ? (
            <p className="text-muted small mb-0">Non disponibile ({rep.err}).</p>
          ) : (
            <div className="d-flex flex-column gap-3">
              {rep.dato?.narrativa ? (
                <div className="md-body" style={{ fontSize: 14 }}>
                  <ReactMarkdown>{rep.dato.narrativa}</ReactMarkdown>
                </div>
              ) : null}
              <div className="row g-3">
                <div className="col-sm-6">
                  <div className="border rounded p-3 h-100">
                    <div className="small text-muted">Investimenti pubblici (OpenCoesione)</div>
                    <div className="h5 mb-0">
                      {rep.dato?.sezioni?.investimenti?.n_progetti ?? 0} progetti
                    </div>
                    <div className="text-primary">
                      {eur(rep.dato?.sezioni?.investimenti?.finanziamento_totale)} finanziati
                    </div>
                  </div>
                </div>
                {rep.dato?.sezioni?.gap_dato?.length ? (
                  <div className="col-sm-6">
                    <div className="border rounded p-3 h-100">
                      <div className="small text-muted mb-1">Gap di dato</div>
                      <ul className="small mb-0" style={{ paddingLeft: 18 }}>
                        {rep.dato.sezioni.gap_dato.map((g, i) => (
                          <li key={i}>{g}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ) : null}
              </div>
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
