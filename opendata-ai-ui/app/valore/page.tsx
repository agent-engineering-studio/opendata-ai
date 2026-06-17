"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { DashboardGate } from "@/components/DashboardGate";

/*
 * Dashboard "Valore del patrimonio" — aggregati dal portfolio (GET /value/portfolio):
 * copertura HVD, licenze aperte, freschezza, riuso. Filtrabile per regione.
 */

type Portfolio = {
  count: number;
  pct_hvd: number | null;
  pct_open_license: number | null;
  avg_freshness_days: number | null;
  avg_stars: number | null;
  avg_reuse: number | null;
};

type Stato =
  | { fase: "idle" }
  | { fase: "loading" }
  | { fase: "errore"; messaggio: string }
  | { fase: "risultato"; portfolio: Portfolio };

function Kpi({ label, value, suffix }: { label: string; value: number | null; suffix?: string }) {
  return (
    <div className="col-6 col-md-4 col-lg-2">
      <div className="border rounded p-3 h-100">
        <div className="h4 mb-0">{value == null ? "—" : `${value}${suffix ?? ""}`}</div>
        <div className="text-slate-500" style={{ fontSize: 13 }}>{label}</div>
      </div>
    </div>
  );
}

function ValoreInner() {
  const { getToken } = useAuth();
  const [region, setRegion] = useState("");
  const [stato, setStato] = useState<Stato>({ fase: "idle" });

  const load = useCallback(async () => {
    setStato({ fase: "loading" });
    try {
      const token = await getToken();
      const qs = region.trim() ? `?region=${encodeURIComponent(region.trim())}` : "";
      const resp = await apiFetch(`/value/portfolio${qs}`, { token });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const portfolio = (await resp.json()) as Portfolio;
      setStato({ fase: "risultato", portfolio });
    } catch (err) {
      setStato({ fase: "errore", messaggio: err instanceof Error ? err.message : String(err) });
    }
  }, [getToken, region]);

  useEffect(() => {
    void load();
    // solo al mount; il refresh con filtro è manuale via bottone
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pf = stato.fase === "risultato" ? stato.portfolio : null;
  const chartData = pf
    ? [
        { k: "% HVD", v: pf.pct_hvd ?? 0 },
        { k: "% Licenza aperta", v: pf.pct_open_license ?? 0 },
        { k: "Reuse medio", v: pf.avg_reuse ?? 0 },
      ]
    : [];

  return (
    <main id="main-content" className="container py-4">
      <h1 className="h3 mb-1">Valore del patrimonio</h1>
      <p className="text-slate-500 mb-3" style={{ fontSize: 14 }}>
        Aggregati di valore dei dataset valutati: alto valore (HVD), apertura, freschezza, riuso.
      </p>

      <div className="d-flex flex-wrap gap-2 mb-4" style={{ maxWidth: 520 }}>
        <input
          type="text"
          className="form-control"
          style={{ flex: 1, minWidth: 200 }}
          placeholder="Filtra per regione (es. Puglia) — opzionale"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
        />
        <button type="button" className="btn btn-primary" onClick={() => void load()}>
          Aggiorna
        </button>
      </div>

      {stato.fase === "loading" ? <p className="text-slate-500">Caricamento…</p> : null}
      {stato.fase === "errore" ? (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700" style={{ fontSize: 14 }}>
          Errore: {stato.messaggio}
        </div>
      ) : null}

      {pf ? (
        <div className="d-flex flex-column gap-4">
          <div className="row g-3">
            <Kpi label="Dataset valutati" value={pf.count} />
            <Kpi label="% Alto valore (HVD)" value={pf.pct_hvd} suffix="%" />
            <Kpi label="% Licenza aperta" value={pf.pct_open_license} suffix="%" />
            <Kpi label="Freschezza media (gg)" value={pf.avg_freshness_days} />
            <Kpi label="Stelle medie" value={pf.avg_stars} />
            <Kpi label="Reuse medio" value={pf.avg_reuse} />
          </div>

          {pf.count > 0 ? (
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="k" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={36} />
                  <Tooltip />
                  <Bar dataKey="v" fill="#2563eb" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-slate-500" style={{ fontSize: 14 }}>
              Nessun dataset valutato per questo filtro. Esegui prima un assessment di maturità
              (pagina Scorecard) per popolare il portfolio.
            </p>
          )}
        </div>
      ) : null}
    </main>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <Suspense fallback={<div className="container py-4 text-slate-500">Caricamento…</div>}>
        <ValoreInner />
      </Suspense>
    </DashboardGate>
  );
}
