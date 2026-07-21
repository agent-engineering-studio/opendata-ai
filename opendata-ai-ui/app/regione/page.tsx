"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { DashboardGate } from "@/components/DashboardGate";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

type Hint = {
  tipo: string;
  motivo: string;
  istat?: string | null;
  nome?: string | null;
  overall?: number | null;
  dimensione?: string | null;
  mediana?: number | null;
};

type Overview = {
  regione: string;
  cod_regione: string;
  comuni_totali: number;
  comuni_valutati: number;
  distribuzione_stato: Record<string, number>;
  mediana_overall: number | null;
  hvd_copertura: Record<string, number>;
  dimensioni_mediana: Record<string, number>;
  dove_intervenire: Hint[];
};

type ComuneRow = {
  istat: string;
  nome: string;
  provincia: string | null;
  overall: number | null;
  stato: string;
  n_dataset: number;
};

type Idea = {
  id: string;
  nome: string;
  area: string;
  hvd: string | null;
  priorita: number;
  comuni_mancanti: number | null;
  comuni_totali: number;
  motivo: string;
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

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="col-6 col-md-3">
      <div className="border rounded p-3 h-100">
        <div className="h3 mb-0">{value}</div>
        <div className="small text-muted">{label}</div>
      </div>
    </div>
  );
}

type TrendPoint = { data: string | null; mediana_overall: number | null };

function Dashboard() {
  const { getToken } = useAuth();
  const [ov, setOv] = useState<Overview | null>(null);
  const [comuni, setComuni] = useState<ComuneRow[] | null>(null);
  const [idee, setIdee] = useState<Idea[] | null>(null);
  const [narrativa, setNarrativa] = useState<string | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const token = await getToken();
      const [o, c, i] = await Promise.all([
        apiFetch("/regione/overview", { token }),
        apiFetch("/regione/comuni", { token }),
        apiFetch("/regione/idee", { token }),
      ]);
      if (!o.ok || !c.ok || !i.ok) throw new Error(`HTTP ${o.status}/${c.status}/${i.status}`);
      setOv(await o.json());
      setComuni((await c.json()).comuni as ComuneRow[]);
      setIdee((await i.json()).idee as Idea[]);
      // Narrativa + trend: extra, non bloccanti.
      apiFetch("/regione/narrativa", { token })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => d && setNarrativa(d.testo))
        .catch(() => {});
      apiFetch("/regione/trend", { token })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => d && setTrend((d.punti ?? []) as TrendPoint[]))
        .catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [getToken]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="alert alert-danger" role="alert">
        Impossibile caricare il cruscotto: {error}
      </div>
    );
  }
  if (!ov || !comuni || !idee) {
    return <p className="text-muted">Caricamento del cruscotto…</p>;
  }

  const dist = ov.distribuzione_stato;
  const distTot = STATI.reduce((s, k) => s + (dist[k] ?? 0), 0) || 1;

  return (
    <>
      <h1 className="h3 mb-1">Cruscotto regionale{ov.regione ? ` · ${ov.regione}` : ""}</h1>
      <p className="text-muted">
        Stato di maturità degli open data dei comuni della regione, dove
        intervenire e priorità di pubblicazione a livello regionale.
      </p>

      {narrativa && (
        <div className="alert alert-light border" role="note">
          {narrativa}
        </div>
      )}

      <div className="row g-3 mb-4">
        <Kpi label="Comuni" value={String(ov.comuni_totali)} />
        <Kpi label="Comuni valutati" value={String(ov.comuni_valutati)} />
        <Kpi
          label="Maturità mediana (ODM)"
          value={ov.mediana_overall != null ? `${ov.mediana_overall.toFixed(0)}/100` : "—"}
        />
        <Kpi label="Comuni maturi" value={String(dist.maturo ?? 0)} />
      </div>

      {/* Distribuzione per stato */}
      <h2 className="h6">Distribuzione dei comuni per stato</h2>
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

      {/* Trend della maturità mediana (F6) */}
      {trend.length >= 2 && (
        <div className="mb-4">
          <h2 className="h6">Andamento della maturità mediana</h2>
          <div style={{ width: "100%", height: 200 }}>
            <ResponsiveContainer>
              <LineChart
                data={trend.map((p, idx) => ({
                  t: p.data ? p.data.slice(0, 10) : String(idx + 1),
                  mediana: p.mediana_overall,
                }))}
              >
                <XAxis dataKey="t" fontSize={11} />
                <YAxis domain={[0, 100]} fontSize={11} width={30} />
                <Tooltip />
                <Line type="monotone" dataKey="mediana" stroke="#0066CC" strokeWidth={2} dot />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Dove intervenire */}
      {ov.dove_intervenire.length > 0 && (
        <div className="mb-4">
          <h2 className="h6">Dove intervenire</h2>
          <ul className="list-group">
            {ov.dove_intervenire.map((h, idx) => (
              <li key={idx} className="list-group-item d-flex justify-content-between align-items-start">
                <span>
                  {h.tipo === "comune" ? (
                    <>
                      <strong>{h.nome}</strong>{" "}
                      <span className="text-muted small">({h.istat})</span>
                    </>
                  ) : (
                    <>
                      Dimensione <strong>{h.dimensione}</strong>
                    </>
                  )}
                  <div className="small text-muted">{h.motivo}</div>
                </span>
                {h.tipo === "comune" && h.istat && (
                  <Link href={`/copilota#${h.istat}`} className="btn btn-sm btn-outline-primary">
                    Apri nel Copilota
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="row g-4">
        {/* Classifica comuni */}
        <div className="col-lg-7">
          <h2 className="h6">Comuni della regione</h2>
          <div className="table-responsive">
            <table className="table table-sm align-middle">
              <thead>
                <tr>
                  <th>Comune</th>
                  <th>Prov.</th>
                  <th>Stato</th>
                  <th className="text-end">ODM</th>
                </tr>
              </thead>
              <tbody>
                {comuni.slice(0, 30).map((c) => (
                  <tr key={c.istat}>
                    <td>
                      <Link href={`/copilota#${c.istat}`} className="text-decoration-none">
                        {c.nome}
                      </Link>
                    </td>
                    <td className="text-muted">{c.provincia ?? "—"}</td>
                    <td>
                      <span className="badge" style={{ background: STATO_COLOR[c.stato] }}>
                        {STATO_LABEL[c.stato] ?? c.stato}
                      </span>
                    </td>
                    <td className="text-end">{c.overall != null ? c.overall.toFixed(0) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {comuni.length > 30 && (
            <p className="small text-muted">Mostrati i primi 30 di {comuni.length}.</p>
          )}
        </div>

        {/* Idee regionali */}
        <div className="col-lg-5">
          <h2 className="h6">Priorità regionali di pubblicazione</h2>
          <ul className="list-group">
            {idee.slice(0, 10).map((i) => (
              <li key={i.id} className="list-group-item">
                <div className="d-flex justify-content-between">
                  <strong>{i.nome}</strong>
                  <span className="badge bg-primary-subtle text-primary-emphasis">
                    {i.priorita.toFixed(0)}
                  </span>
                </div>
                <div className="small text-muted">{i.motivo}</div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <div className="container py-4" style={{ maxWidth: 1080 }}>
        <Dashboard />
      </div>
    </DashboardGate>
  );
}
