"use client";

import { Suspense, useEffect, useState } from "react";
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
 * Galleria use case (Fase 3): ApriQui AI (attrattività) e PugliaTrip Brain
 * (itinerari meteo-aware), più gli showcase dichiarativi. Tutto per codice ISTAT
 * (qualunque comune italiano).
 */

type Category = { category: string; score: number; opportunity: number; demand: number };
type ApriQui = {
  locations: { name: string; population: number | null; categories: Category[]; top: Category[] }[];
  explanation: string;
};

type Poi = { name: string; kind: string };
type Day = { date: string; weather: { label: string; tmax: number | null; outdoor_ok: boolean }; pois: Poi[] };
type Trip = {
  place: { name: string };
  center: { lat: number; lon: number } | null;
  n_pois: number;
  n_stops: number;
  itinerary: Day[];
  explanation: string;
};

type Showcase = { id: string; title: string; description: string; visualization: { type: string } };

function osmEmbed(lat: number, lon: number): string {
  const d = 0.06;
  const bbox = `${lon - d},${lat - d},${lon + d},${lat + d}`;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`;
}

function UseCasesInner() {
  const { getToken } = useAuth();
  const [istat, setIstat] = useState("072021");
  const [showcases, setShowcases] = useState<Showcase[]>([]);
  const [apriqui, setApriqui] = useState<ApriQui | null>(null);
  const [trip, setTrip] = useState<Trip | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        const r = await apiFetch("/showcases", { token });
        if (r.ok) setShowcases(((await r.json()).showcases ?? []) as Showcase[]);
      } catch {
        /* galleria showcase best-effort */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function post<T>(path: string, body: unknown, tag: string): Promise<T | null> {
    setBusy(tag);
    setErr(null);
    try {
      const token = await getToken();
      const r = await apiFetch(path, { method: "POST", token, body: JSON.stringify(body) });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return (await r.json()) as T;
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function runApriqui() {
    const out = await post<ApriQui>("/usecases/apriqui", { istat_codes: [istat.trim()] }, "apriqui");
    if (out) setApriqui(out);
  }
  async function runTrip() {
    const out = await post<Trip>("/usecases/pugliatrip", { istat_code: istat.trim(), days: 3 }, "trip");
    if (out) setTrip(out);
  }

  const aqChart = apriqui?.locations[0]?.top.map((c) => ({ k: c.category, v: c.score })) ?? [];

  return (
    <main id="main-content" className="container py-4">
      <h1 className="h3 mb-1">Casi d&apos;uso</h1>
      <p className="text-slate-500 mb-3" style={{ fontSize: 14 }}>
        Applicazioni costruite sul patrimonio dati: attrattività commerciale e itinerari
        turistici meteo-aware. Per qualunque comune (codice ISTAT).
      </p>

      <div className="d-flex flex-wrap gap-2 mb-4" style={{ maxWidth: 460 }}>
        <input
          className="form-control"
          style={{ flex: 1, minWidth: 160 }}
          placeholder="Codice ISTAT (es. 072021)"
          value={istat}
          onChange={(e) => setIstat(e.target.value)}
        />
        <button className="btn btn-primary" onClick={runApriqui} disabled={busy !== null}>
          {busy === "apriqui" ? "…" : "ApriQui"}
        </button>
        <button className="btn btn-outline-primary" onClick={runTrip} disabled={busy !== null}>
          {busy === "trip" ? "…" : "PugliaTrip"}
        </button>
      </div>

      {err ? (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700 mb-3" style={{ fontSize: 14 }}>
          Errore: {err}
        </div>
      ) : null}

      <div className="row g-4">
        {/* ApriQui */}
        {apriqui?.locations[0] ? (
          <section className="col-lg-6">
            <h2 className="h5">ApriQui AI — {apriqui.locations[0].name}</h2>
            <div style={{ height: 240 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={aqChart} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="k" tick={{ fontSize: 10 }} width={150} />
                  <Tooltip />
                  <Bar dataKey="v" fill="#2563eb" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p style={{ fontSize: 14 }}>{apriqui.explanation}</p>
          </section>
        ) : null}

        {/* PugliaTrip */}
        {trip ? (
          <section className="col-lg-6">
            <h2 className="h5">PugliaTrip Brain — {trip.place.name}</h2>
            {trip.center ? (
              <iframe
                title="map"
                style={{ width: "100%", height: 220, border: "1px solid #e2e8f0", borderRadius: 6 }}
                src={osmEmbed(trip.center.lat, trip.center.lon)}
              />
            ) : null}
            <p className="text-slate-500 mb-1" style={{ fontSize: 13 }}>
              {trip.n_pois} luoghi · {trip.n_stops} fermate TPL
            </p>
            {trip.itinerary.map((d) => (
              <div key={d.date} className="mb-2">
                <strong style={{ fontSize: 14 }}>
                  {d.date} · {d.weather.label} {d.weather.tmax != null ? `(${d.weather.tmax}°)` : ""}
                </strong>
                <ul className="small mb-0">
                  {d.pois.length ? d.pois.map((p) => <li key={p.name}>{p.name} <span className="text-slate-400">({p.kind})</span></li>)
                    : <li className="text-slate-400">nessun POI</li>}
                </ul>
              </div>
            ))}
            <p style={{ fontSize: 14 }}>{trip.explanation}</p>
          </section>
        ) : null}
      </div>

      {/* Showcase dichiarativi */}
      <section className="mt-4">
        <h2 className="h5">Showcase</h2>
        <div className="row g-3">
          {showcases.map((s) => (
            <div key={s.id} className="col-md-4">
              <div className="border rounded p-3 h-100">
                <h3 className="h6 mb-1">{s.title}</h3>
                <p className="small text-slate-600 mb-1">{s.description}</p>
                <code className="small text-slate-400">{s.id} · {s.visualization?.type}</code>
              </div>
            </div>
          ))}
          {showcases.length === 0 ? <p className="text-slate-500 small">Nessuno showcase.</p> : null}
        </div>
      </section>
    </main>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <Suspense fallback={<div className="container py-4 text-slate-500">Caricamento…</div>}>
        <UseCasesInner />
      </Suspense>
    </DashboardGate>
  );
}
