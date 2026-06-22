"use client";

import { useRef, useState } from "react";

import { apiFetch, proxyFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DashboardGate } from "@/components/DashboardGate";

// ─── tipi del report restituito da POST /quality/profile ───
type Finding = { livello: "alto" | "medio" | "basso"; codice: string; messaggio: string; colonna?: string };
type ColonnaProfilo = {
  nome: string; tipo: string; vuoti_pct: number; distinti: number; esempi: string[]; problemi: string[];
};
type CsvReport = {
  format: "CSV";
  righe: number; colonne: number; separatore: string | null;
  colonne_profilo: ColonnaProfilo[];
  findings: Finding[]; punteggio: number;
};
type GeoReport = {
  format: "GEOJSON";
  tipo: string | null; features: number; geometrie: Record<string, number>;
  crs: string | null; crs_wgs84: boolean; bbox: number[] | null;
  findings: Finding[]; punteggio: number;
};
type Report = CsvReport | GeoReport;

const LIVELLO: Record<Finding["livello"], { label: string; badge: string; ord: number }> = {
  alto: { label: "Critico", badge: "bg-danger", ord: 0 },
  medio: { label: "Da sistemare", badge: "bg-warning text-dark", ord: 1 },
  basso: { label: "Minore", badge: "bg-secondary", ord: 2 },
};

function scoreColor(p: number): string {
  if (p >= 80) return "text-success";
  if (p >= 50) return "text-warning";
  return "text-danger";
}

const ESEMPIO_CSV =
  "comune;popolazione;data rilevazione\nGioia del Colle;27.889;01/01/2023\nBari;320475;2023-01-01\nModugno;;2023-01-01\n";

function QualitaInner() {
  const { getToken } = useAuth();
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [fixing, setFixing] = useState(false);
  const [fixChanges, setFixChanges] = useState<{ codice: string; messaggio: string }[] | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => { setText(String(reader.result ?? "")); setUrl(""); };
    reader.readAsText(f);
  }

  function _body(): { content: string } | { url: string } | null {
    return text.trim() ? { content: text } : url.trim() ? { url: url.trim() } : null;
  }

  function _download(content: string, name: string, mime: string) {
    const blob = new Blob([content], { type: mime });
    const dlUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = dlUrl;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(dlUrl);
  }

  // CSV: auto-fix server-side (POST /quality/fix)
  async function scaricaCsvCorretto() {
    const body = _body();
    if (!body) return;
    setFixing(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await apiFetch("/quality/fix", { method: "POST", token, body: JSON.stringify(body) });
      if (!res.ok) {
        let msg = `Errore ${res.status}`;
        try { const j = await res.json(); if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg; } catch { /* */ }
        setError(msg);
        return;
      }
      const data = (await res.json()) as { content: string; changes: { codice: string; messaggio: string }[] };
      setFixChanges(data.changes);
      _download(data.content, "dati-corretti.csv", "text/csv;charset=utf-8");
    } catch (e) {
      setError(`Errore di rete: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setFixing(false);
    }
  }

  // GeoJSON: riproiezione in WGS84 lato browser (proj4 via toWgs84)
  async function scaricaGeoWgs84() {
    setFixing(true);
    setError(null);
    try {
      let raw = text.trim();
      if (!raw && url.trim()) {
        const r = await proxyFetch(url.trim(), { getToken });
        if (!r.ok) { setError(`Errore scaricando l'URL: ${r.status}`); return; }
        raw = await r.text();
      }
      if (!raw) return;
      let obj: Record<string, unknown>;
      try { obj = JSON.parse(raw); } catch { setError("GeoJSON non valido."); return; }
      const { toWgs84 } = await import("@/lib/geoReproject");
      const wgs = toWgs84(obj);
      _download(JSON.stringify(wgs), "dati-wgs84.geojson", "application/geo+json;charset=utf-8");
      const giaWgs84 = report?.format === "GEOJSON" && report.crs_wgs84;
      setFixChanges([{
        codice: "wgs84",
        messaggio: giaWgs84
          ? "File già in WGS84: scaricata una copia normalizzata (EPSG:4326)."
          : "File riproiettato in WGS84 (EPSG:4326): ora le geometrie compaiono correttamente sulla mappa.",
      }]);
    } catch (e) {
      setError(`Errore: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setFixing(false);
    }
  }

  async function analizza() {
    setLoading(true);
    setError(null);
    setReport(null);
    setFixChanges(null);
    try {
      const body = _body();
      if (!body) {
        setError("Incolla un CSV/GeoJSON, carica un file oppure indica un URL.");
        return;
      }
      const token = await getToken();
      const res = await apiFetch("/quality/profile", { method: "POST", token, body: JSON.stringify(body) });
      if (!res.ok) {
        let msg = `Errore ${res.status}`;
        try { const j = await res.json(); if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg; } catch { /* */ }
        setError(msg);
        return;
      }
      setReport((await res.json()) as Report);
    } catch (e) {
      setError(`Errore di rete: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }

  const findingsOrdinati = report
    ? [...report.findings].sort((a, b) => LIVELLO[a.livello].ord - LIVELLO[b.livello].ord)
    : [];
  const geo = report?.format === "GEOJSON" ? report : null;
  const csv = report?.format === "CSV" ? report : null;

  return (
    <div className="container py-4" style={{ maxWidth: 980 }}>
      <h1 className="h3 mb-1">Qualità dei dati</h1>
      <p className="text-muted">
        Incolla un <strong>CSV</strong> o un <strong>GeoJSON</strong> (o caricane il file, o indica
        un URL pubblico) e ricevi una diagnosi automatica: per le tabelle tipo colonne, valori
        mancanti e problemi; per i dati geografici il <strong>sistema di coordinate</strong> e la
        validità delle geometrie. Più un punteggio. Tutto deterministico, nessun dato inventato.
      </p>

      {/* INPUT */}
      <div className="card shadow-sm mb-4">
        <div className="card-body">
          <label className="form-label fw-semibold" htmlFor="src">Contenuto (CSV o GeoJSON)</label>
          <textarea
            id="src"
            className="form-control font-monospace"
            style={{ minHeight: 160, fontSize: ".85rem" }}
            placeholder={'comune,popolazione,data\nBari,320475,2023-01-01\n\noppure  {"type":"FeatureCollection", ...}'}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="d-flex flex-wrap align-items-center gap-2 mt-2">
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => fileRef.current?.click()}>
              Carica file…
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.tsv,.txt,.geojson,.json,text/csv,application/geo+json,application/json"
              className="d-none"
              onChange={onFile}
            />
            <button type="button" className="btn btn-sm btn-link text-muted" onClick={() => { setText(ESEMPIO_CSV); setUrl(""); }}>
              Usa un esempio CSV
            </button>
            <span className="text-muted small ms-auto">oppure</span>
          </div>
          <input
            type="url"
            className="form-control mt-2"
            placeholder="https://… (URL pubblico di un CSV o GeoJSON)"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <div className="d-flex align-items-center gap-3 mt-3">
            <button type="button" className="btn btn-primary" onClick={analizza} disabled={loading}>
              {loading ? "Analizzo…" : "Analizza"}
            </button>
            {(text || url || report) && (
              <button
                type="button"
                className="btn btn-link text-muted p-0"
                onClick={() => { setText(""); setUrl(""); setReport(null); setError(null); setFixChanges(null); }}
              >
                Pulisci
              </button>
            )}
          </div>
          {error && <div className="alert alert-danger mt-3 mb-0">{error}</div>}
        </div>
      </div>

      {/* REPORT */}
      {report && (
        <>
          <div className="card shadow-sm mb-4">
            <div className="card-body d-flex flex-wrap align-items-center gap-4">
              <div className="text-center">
                <div className={`display-4 fw-bold ${scoreColor(report.punteggio)}`}>{report.punteggio}</div>
                <div className="text-muted small">punteggio / 100</div>
              </div>

              {csv && (
                <ul className="list-unstyled mb-0 small text-muted">
                  <li><strong>{csv.righe.toLocaleString("it-IT")}</strong> righe · <strong>{csv.colonne}</strong> colonne</li>
                  <li>Separatore rilevato: <code>{csv.separatore === "\t" ? "\\t (tab)" : csv.separatore}</code></li>
                  <li>{csv.findings.length} segnalazion{csv.findings.length === 1 ? "e" : "i"}</li>
                </ul>
              )}
              {geo && (
                <ul className="list-unstyled mb-0 small text-muted">
                  <li>
                    <strong>{geo.features.toLocaleString("it-IT")}</strong> feature ·{" "}
                    {Object.entries(geo.geometrie).map(([t, n]) => `${n} ${t}`).join(", ") || "—"}
                  </li>
                  <li>
                    CRS:{" "}
                    {geo.crs_wgs84 ? (
                      <span className="text-success fw-semibold">WGS84 ✓</span>
                    ) : (
                      <span className="text-danger fw-semibold">{geo.crs} — da riproiettare</span>
                    )}
                  </li>
                  <li>{geo.findings.length} segnalazion{geo.findings.length === 1 ? "e" : "i"}</li>
                </ul>
              )}

              <div className="ms-auto text-end">
                {csv && (
                  <>
                    <button type="button" className="btn btn-success" onClick={scaricaCsvCorretto} disabled={fixing}>
                      {fixing ? "Preparo…" : "⬇ Scarica versione corretta"}
                    </button>
                    <div className="text-muted small mt-1" style={{ maxWidth: 240 }}>
                      Correzioni sicure: intestazioni, spazi, date ISO, decimali, separatore.
                    </div>
                  </>
                )}
                {geo && (
                  <>
                    <button type="button" className="btn btn-success" onClick={scaricaGeoWgs84} disabled={fixing}>
                      {fixing ? "Preparo…" : "⬇ Scarica in WGS84"}
                    </button>
                    <div className="text-muted small mt-1" style={{ maxWidth: 240 }}>
                      Riproietta in WGS84 (EPSG:4326), pronto per la mappa.
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          {fixChanges && (
            <div className="alert alert-success">
              {fixChanges.length === 0 ? (
                <span>Il file era già pulito: nessuna correzione necessaria. Scaricata una copia standard (UTF-8, separatore virgola).</span>
              ) : (
                <>
                  <strong>Esito:</strong>
                  <ul className="mb-0 mt-2">
                    {fixChanges.map((c) => (<li key={c.codice}>{c.messaggio}</li>))}
                  </ul>
                </>
              )}
            </div>
          )}

          {findingsOrdinati.length > 0 && (
            <div className="card shadow-sm mb-4">
              <div className="card-body">
                <h2 className="h5 mb-3">Cosa migliorare</h2>
                <ul className="list-group list-group-flush">
                  {findingsOrdinati.map((f, i) => (
                    <li key={i} className="list-group-item px-0 d-flex gap-2 align-items-start">
                      <span className={`badge ${LIVELLO[f.livello].badge} flex-shrink-0`} style={{ minWidth: 96 }}>
                        {LIVELLO[f.livello].label}
                      </span>
                      <span>
                        {f.messaggio}
                        {f.colonna && <span className="text-muted"> — colonna <code>{f.colonna}</code></span>}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {csv && (
            <div className="card shadow-sm">
              <div className="card-body">
                <h2 className="h5 mb-3">Profilo delle colonne</h2>
                <div className="table-responsive">
                  <table className="table table-sm align-middle">
                    <thead>
                      <tr className="text-muted small text-uppercase">
                        <th>Colonna</th><th>Tipo</th><th className="text-end">Vuoti</th>
                        <th className="text-end">Distinti</th><th>Esempi</th><th>Problemi</th>
                      </tr>
                    </thead>
                    <tbody>
                      {csv.colonne_profilo.map((c) => (
                        <tr key={c.nome}>
                          <td className="fw-semibold">{c.nome}</td>
                          <td><span className="badge bg-light text-dark border">{c.tipo}</span></td>
                          <td className={`text-end ${c.vuoti_pct >= 20 ? "text-danger fw-semibold" : ""}`}>{c.vuoti_pct}%</td>
                          <td className="text-end">{c.distinti}</td>
                          <td className="small text-muted text-truncate" style={{ maxWidth: 220 }}>{c.esempi.join(", ")}</td>
                          <td className="small">
                            {c.problemi.length ? c.problemi.join("; ") : <span className="text-success">—</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {geo && (
            <div className="card shadow-sm">
              <div className="card-body">
                <h2 className="h5 mb-3">Dettaglio geografico</h2>
                <ul className="list-unstyled small mb-0">
                  <li><strong>Tipo GeoJSON:</strong> {geo.tipo ?? "—"}</li>
                  <li><strong>Sistema di coordinate:</strong> {geo.crs ?? "—"} {geo.crs_wgs84 ? "(ok per la mappa)" : "(va riproiettato in WGS84)"}</li>
                  <li>
                    <strong>Geometrie:</strong>{" "}
                    {Object.entries(geo.geometrie).map(([t, n]) => `${n}× ${t}`).join(", ") || "—"}
                  </li>
                  {geo.bbox && (
                    <li><strong>Area coperta (bbox):</strong> <code>{geo.bbox.join(", ")}</code></li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <QualitaInner />
    </DashboardGate>
  );
}
