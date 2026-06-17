"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
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
 * Report Territorio (modello canonico): POST /territory/report → profilo,
 * investimenti, servizi/accessibilità, segnali, gap di dato + narrazione Sonnet.
 */

type PerTema = { tema: string; finanziamento: number };
type Report = {
  place: { id: number; istat_code: string; name: string };
  generato_il: string;
  narrativa: string;
  sezioni: {
    profilo: Record<string, Record<string, unknown>>;
    investimenti: { n_progetti: number; finanziamento_totale: number; per_tema: PerTema[] };
    servizi_accessibilita: { commercio: Record<string, number>; turismo_cultura: Record<string, number> };
    gap_dato: string[];
    idee_sviluppo: unknown[];
  };
};

type Stato =
  | { fase: "idle" }
  | { fase: "loading" }
  | { fase: "errore"; messaggio: string }
  | { fase: "risultato"; report: Report };

function euro(n: number): string {
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
}

function ReportInner() {
  const { getToken } = useAuth();
  const params = useSearchParams();
  const [istat, setIstat] = useState(params.get("istat") ?? "072021");
  const [stato, setStato] = useState<Stato>({ fase: "idle" });

  async function genera(e?: React.FormEvent) {
    e?.preventDefault();
    const code = istat.trim();
    if (!code) return;
    setStato({ fase: "loading" });
    try {
      const token = await getToken();
      const resp = await apiFetch("/territory/report", {
        method: "POST",
        token,
        body: JSON.stringify({ istat_code: code }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setStato({ fase: "risultato", report: (await resp.json()) as Report });
    } catch (err) {
      setStato({ fase: "errore", messaggio: err instanceof Error ? err.message : String(err) });
    }
  }

  const report = stato.fase === "risultato" ? stato.report : null;
  const temaData = report?.sezioni.investimenti.per_tema.slice(0, 8) ?? [];

  return (
    <main id="main-content" className="container py-4">
      <h1 className="h3 mb-1">Report Territorio</h1>
      <p className="text-slate-500 mb-3" style={{ fontSize: 14 }}>
        Profilo, investimenti pubblici, servizi e gap di dato di un comune (codice ISTAT).
      </p>

      <form onSubmit={genera} className="d-flex flex-wrap gap-2 mb-4" style={{ maxWidth: 420 }}>
        <input
          type="text"
          className="form-control"
          style={{ flex: 1, minWidth: 160 }}
          placeholder="Codice ISTAT (es. 072021)"
          value={istat}
          onChange={(ev) => setIstat(ev.target.value)}
        />
        <button type="submit" className="btn btn-primary" disabled={stato.fase === "loading"}>
          {stato.fase === "loading" ? "Generazione…" : "Genera report"}
        </button>
      </form>

      {stato.fase === "errore" ? (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700" style={{ fontSize: 14 }}>
          Errore: {stato.messaggio}
        </div>
      ) : null}

      {report ? (
        <div className="d-flex flex-column gap-4">
          <div>
            <h2 className="h4 mb-1">{report.place.name}</h2>
            <span className="text-slate-500" style={{ fontSize: 13 }}>
              ISTAT {report.place.istat_code}
            </span>
          </div>

          <section>
            <h3 className="h6 text-slate-500">Sintesi</h3>
            <p style={{ fontSize: 15 }}>{report.narrativa}</p>
          </section>

          <div className="row g-4">
            <div className="col-md-6">
              <h3 className="h6 text-slate-500">Investimenti pubblici (OpenCoesione)</h3>
              <p className="mb-2" style={{ fontSize: 14 }}>
                {report.sezioni.investimenti.n_progetti} progetti ·{" "}
                {euro(report.sezioni.investimenti.finanziamento_totale)}
              </p>
              {temaData.length ? (
                <div style={{ height: 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={temaData} layout="vertical" margin={{ left: 24 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis type="number" tick={{ fontSize: 10 }} />
                      <YAxis type="category" dataKey="tema" tick={{ fontSize: 10 }} width={120} />
                      <Tooltip formatter={(v: number) => euro(v)} />
                      <Bar dataKey="finanziamento" fill="#059669" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-slate-500" style={{ fontSize: 14 }}>Nessun progetto tracciato.</p>
              )}
            </div>

            <div className="col-md-6">
              <h3 className="h6 text-slate-500">Servizi / accessibilità (OSM)</h3>
              <p style={{ fontSize: 14 }} className="mb-1">
                Commercio: {report.sezioni.servizi_accessibilita.commercio?.totale ?? "—"} · Turismo/cultura:{" "}
                {report.sezioni.servizi_accessibilita.turismo_cultura?.totale ?? "—"}
              </p>
              <h3 className="h6 text-slate-500 mt-3">Gap di dato</h3>
              <ul className="small text-slate-600">
                {report.sezioni.gap_dato.length
                  ? report.sezioni.gap_dato.map((g, i) => <li key={i}>{g}</li>)
                  : <li>Nessun gap rilevante.</li>}
              </ul>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <Suspense fallback={<div className="container py-4 text-slate-500">Caricamento…</div>}>
        <ReportInner />
      </Suspense>
    </DashboardGate>
  );
}
