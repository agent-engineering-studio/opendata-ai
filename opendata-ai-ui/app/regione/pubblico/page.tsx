"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

// Vista PUBBLICA di trasparenza (#232, F5): read-only, senza login. Consuma
// l'unico endpoint pubblico /regione/pubblico (aggregati, no dati personali).
// Nessun DashboardGate, nessun token.

type Pub = {
  regione: string;
  comuni_totali: number;
  comuni_valutati: number;
  distribuzione_stato: Record<string, number>;
  mediana_overall: number | null;
  hvd_copertura: Record<string, number>;
  comuni: { nome: string; provincia: string | null; stato: string }[];
  idee_top: { nome: string; priorita: number; motivo: string }[];
};

const STATO_LABEL: Record<string, string> = {
  zero_dati: "Zero dati",
  pochi_dati: "Pochi dati",
  in_crescita: "In crescita",
  maturo: "Maturo",
};
const STATO_COLOR: Record<string, string> = {
  zero_dati: "#D9364F",
  pochi_dati: "#E58A00",
  in_crescita: "#0066CC",
  maturo: "#008758",
};
const STATI = ["zero_dati", "pochi_dati", "in_crescita", "maturo"] as const;
const HVD_LABEL: Record<string, string> = {
  geospatial: "Geospaziale",
  earth_observation_environment: "Ambiente",
  meteorological: "Meteo",
  statistics: "Statistica",
  companies_ownership: "Imprese",
  mobility: "Mobilità",
};

export default function Page() {
  const [data, setData] = useState<Pub | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await apiFetch("/regione/pubblico");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (alive) setData(await res.json());
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (error) {
    return (
      <div className="container py-5">
        <div className="alert alert-danger">Dati non disponibili: {error}</div>
      </div>
    );
  }
  if (!data) return <div className="container py-5 text-muted">Caricamento…</div>;

  const dist = data.distribuzione_stato;
  const distTot = STATI.reduce((s, k) => s + (dist[k] ?? 0), 0) || 1;

  return (
    <div className="container py-4" style={{ maxWidth: 900 }}>
      <h1 className="h3 mb-1">
        Open data della regione{data.regione ? ` · ${data.regione}` : ""}
      </h1>
      <p className="text-muted">
        Trasparenza pubblica: quanto i comuni della regione pubblicano e
        mantengono i propri dati aperti. Dati aggregati, sola lettura.
      </p>

      <div className="row g-3 my-3">
        <div className="col-6 col-md-3">
          <div className="border rounded p-3">
            <div className="h4 mb-0">{data.comuni_totali}</div>
            <div className="small text-muted">Comuni</div>
          </div>
        </div>
        <div className="col-6 col-md-3">
          <div className="border rounded p-3">
            <div className="h4 mb-0">{data.comuni_valutati}</div>
            <div className="small text-muted">Comuni valutati</div>
          </div>
        </div>
        <div className="col-6 col-md-3">
          <div className="border rounded p-3">
            <div className="h4 mb-0">
              {data.mediana_overall != null ? `${data.mediana_overall.toFixed(0)}/100` : "—"}
            </div>
            <div className="small text-muted">Maturità mediana</div>
          </div>
        </div>
        <div className="col-6 col-md-3">
          <div className="border rounded p-3">
            <div className="h4 mb-0">{dist.maturo ?? 0}</div>
            <div className="small text-muted">Comuni maturi</div>
          </div>
        </div>
      </div>

      <div className="d-flex rounded overflow-hidden mb-2" style={{ height: 22 }}>
        {STATI.map((k) =>
          dist[k] ? (
            <div
              key={k}
              style={{ width: `${((dist[k] ?? 0) / distTot) * 100}%`, background: STATO_COLOR[k] }}
              title={`${STATO_LABEL[k]}: ${dist[k]}`}
            />
          ) : null,
        )}
      </div>
      <div className="d-flex flex-wrap gap-3 small mb-4">
        {STATI.map((k) => (
          <span key={k}>
            <span
              className="d-inline-block rounded-circle me-1"
              style={{ width: 10, height: 10, background: STATO_COLOR[k] }}
            />
            {STATO_LABEL[k]}: <strong>{dist[k] ?? 0}</strong>
          </span>
        ))}
      </div>

      {data.idee_top.length > 0 && (
        <div className="mb-4">
          <h2 className="h6">Dataset prioritari per la regione</h2>
          <ol className="mb-0">
            {data.idee_top.map((i) => (
              <li key={i.nome}>
                <strong>{i.nome}</strong> — <span className="text-muted">{i.motivo}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <h2 className="h6">Copertura per categoria di dati (HVD)</h2>
      <ul className="list-unstyled mb-4">
        {Object.entries(data.hvd_copertura).map(([cat, frac]) => (
          <li key={cat} className="mb-1">
            <span className="d-inline-block" style={{ width: 130 }}>
              {HVD_LABEL[cat] ?? cat}
            </span>
            <span className="badge bg-primary-subtle text-primary-emphasis">
              {(frac * 100).toFixed(0)}%
            </span>
          </li>
        ))}
      </ul>

      <h2 className="h6">Stato dei comuni</h2>
      <div className="d-flex flex-wrap gap-2">
        {data.comuni.map((c) => (
          <span
            key={c.nome}
            className="badge"
            style={{ background: STATO_COLOR[c.stato] }}
            title={STATO_LABEL[c.stato] ?? c.stato}
          >
            {c.nome}
          </span>
        ))}
      </div>
    </div>
  );
}
