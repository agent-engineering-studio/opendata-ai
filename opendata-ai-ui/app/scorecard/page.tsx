"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { DashboardGate } from "@/components/DashboardGate";

/*
 * Scorecard di maturità open-data di un ente (ODM 2025).
 * POST /maturity/assess restituisce: 4 dimensioni, livello, raccomandazioni,
 * trend storico e mediana del cluster.
 */

type Recommendation = {
  code: string;
  severity: string;
  dimension: string;
  message: string;
  affected_count: number;
};

type Scorecard = {
  entity: { id: number; name: string; type: string | null; region: string | null };
  assessed_at: string;
  level: string;
  overall: number;
  dimensions: { policy: number; portal: number; quality: number; impact: number };
  recommendations: Recommendation[];
  n_datasets: number | null;
  truncated: boolean | null;
  trend: { assessed_at: string; overall: number; level: string }[];
  cluster_median: number | null;
};

type Stato =
  | { fase: "idle" }
  | { fase: "loading" }
  | { fase: "errore"; messaggio: string }
  | { fase: "risultato"; scorecard: Scorecard };

const LEVEL_COLOR: Record<string, string> = {
  Beginner: "#dc2626",
  Follower: "#d97706",
  "Fast-tracker": "#2563eb",
  "Trend-setter": "#059669",
};

const SEVERITY_COLOR: Record<string, string> = {
  alta: "#dc2626",
  media: "#d97706",
  bassa: "#64748b",
};

function shortDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("it-IT", { day: "2-digit", month: "short", year: "2-digit" });
  } catch {
    return iso;
  }
}

function ScorecardInner() {
  const { getToken } = useAuth();
  const params = useSearchParams();
  const [entity, setEntity] = useState(params.get("entity") ?? "");
  const [stato, setStato] = useState<Stato>({ fase: "idle" });

  async function assess(e?: React.FormEvent) {
    e?.preventDefault();
    const name = entity.trim();
    if (!name) return;
    setStato({ fase: "loading" });
    try {
      const token = await getToken();
      const resp = await apiFetch("/maturity/assess", {
        method: "POST",
        token,
        body: JSON.stringify({ entity: name }),
      });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const scorecard = (await resp.json()) as Scorecard;
      setStato({ fase: "risultato", scorecard });
    } catch (err) {
      setStato({ fase: "errore", messaggio: err instanceof Error ? err.message : String(err) });
    }
  }

  return (
    <main id="main-content" className="container py-4">
      <h1 className="h3 mb-1">Scorecard di maturità open-data</h1>
      <p className="text-slate-500 mb-3" style={{ fontSize: 14 }}>
        Valutazione ODM 2025 di un ente: qualità dei dati, policy, portale e impatto.
      </p>

      <form onSubmit={assess} className="d-flex flex-wrap gap-2 mb-4" style={{ maxWidth: 640 }}>
        <input
          type="text"
          className="form-control"
          style={{ flex: 1, minWidth: 240 }}
          placeholder="Organizzazione CKAN dell'ente (es. comune-di-gioia-del-colle)"
          value={entity}
          onChange={(ev) => setEntity(ev.target.value)}
        />
        <button type="submit" className="btn btn-primary" disabled={stato.fase === "loading"}>
          {stato.fase === "loading" ? "Valutazione…" : "Valuta"}
        </button>
      </form>

      {stato.fase === "errore" ? (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700" style={{ fontSize: 14 }}>
          Errore nell&apos;assessment: {stato.messaggio}
        </div>
      ) : null}

      {stato.fase === "risultato" ? <ScorecardView scorecard={stato.scorecard} /> : null}
    </main>
  );
}

function ScorecardView({ scorecard }: { scorecard: Scorecard }) {
  const { dimensions, level, overall, cluster_median, trend, recommendations } = scorecard;
  const radarData = [
    { dim: "Policy", value: dimensions.policy },
    { dim: "Portale", value: dimensions.portal },
    { dim: "Qualità", value: dimensions.quality },
    { dim: "Impatto", value: dimensions.impact },
  ];
  const trendData = trend.map((t) => ({ date: shortDate(t.assessed_at), overall: t.overall }));
  const levelColor = LEVEL_COLOR[level] ?? "#334155";

  return (
    <div className="d-flex flex-column gap-4">
      {/* Header */}
      <div className="d-flex flex-wrap align-items-center gap-3">
        <div>
          <h2 className="h4 mb-0">{scorecard.entity.name}</h2>
          <span className="text-slate-500" style={{ fontSize: 13 }}>
            {scorecard.entity.type ?? "ente"}
            {scorecard.entity.region ? ` · ${scorecard.entity.region}` : ""} ·{" "}
            {scorecard.n_datasets ?? 0} dataset valutati
            {scorecard.truncated ? " (campione)" : ""}
          </span>
        </div>
        <span
          className="badge rounded-pill px-3 py-2"
          style={{ backgroundColor: levelColor, color: "white", fontSize: 14 }}
        >
          {level} · {overall.toFixed(0)}/100
        </span>
      </div>

      <div className="row g-4">
        {/* Radar 4 dimensioni */}
        <div className="col-lg-6">
          <h3 className="h6 text-slate-500">Dimensioni</h3>
          <div style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} outerRadius="70%">
                <PolarGrid />
                <PolarAngleAxis dataKey="dim" tick={{ fontSize: 12 }} />
                <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Radar dataKey="value" stroke="#2563eb" fill="#2563eb" fillOpacity={0.4} />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Trend + confronto cluster */}
        <div className="col-lg-6">
          <h3 className="h6 text-slate-500">
            Trend storico{cluster_median != null ? ` · mediana cluster ${cluster_median.toFixed(0)}` : ""}
          </h3>
          <div style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={36} />
                <Tooltip />
                {cluster_median != null ? (
                  <ReferenceLine y={cluster_median} stroke="#94a3b8" strokeDasharray="4 4" />
                ) : null}
                <Line type="monotone" dataKey="overall" stroke="#059669" strokeWidth={2} dot />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Raccomandazioni */}
      <div>
        <h3 className="h6 text-slate-500">Raccomandazioni</h3>
        {recommendations.length === 0 ? (
          <p className="text-slate-500" style={{ fontSize: 14 }}>
            Nessuna raccomandazione: l&apos;ente soddisfa le soglie principali.
          </p>
        ) : (
          <ul className="list-unstyled d-flex flex-column gap-2">
            {recommendations.map((r) => (
              <li key={r.code} className="d-flex align-items-start gap-2">
                <span
                  className="badge rounded-pill"
                  style={{ backgroundColor: SEVERITY_COLOR[r.severity] ?? "#64748b", color: "white" }}
                >
                  {r.severity}
                </span>
                <span style={{ fontSize: 14 }}>
                  {r.message}
                  <span className="text-slate-400"> · {r.dimension}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <Suspense fallback={<div className="container py-4 text-slate-500">Caricamento…</div>}>
        <ScorecardInner />
      </Suspense>
    </DashboardGate>
  );
}
