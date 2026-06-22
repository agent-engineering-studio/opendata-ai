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
type DcatResult = {
  dataset: Record<string, unknown>;
  schema_campi: { nome: string; tipo_xsd: string }[];
  campi_mancanti: string[];
};
type ValidationResult = {
  valido: boolean;
  findings: { livello: "alto" | "medio" | "basso"; codice: string; messaggio: string; campo: string }[];
  licenza: { dichiarata: string | null; aperta: boolean | null; suggerita: string | null };
  fair: { findable: number; accessible: number; interoperable: number; reusable: number; overall: number };
};
type SchemaResult = {
  table_name: string;
  row_estimate: number;
  columns: { name: string; original: string; sql_type: string; nullable: boolean; is_primary_key: boolean; note: string | null }[];
  primary_key: string | null;
  surrogate_key: boolean;
  indexes: { column: string; reason: string }[];
  ddl: string;
  notes: string[];
};
type ConvertResult = {
  ok: boolean;
  error: string | null;
  lat_field?: string | null;
  lon_field?: string | null;
  geojson: Record<string, unknown> | null;
  n_features: number;
  n_skipped: number;
  candidate_columns?: string[];
  warnings?: string[];
};
type SummaryResult = {
  righe: number;
  numeric: { column: string; conteggio: number; min: number; max: number; media: number; somma: number }[];
  categorie: { column: string; distinti: number; altri: number; top: { valore: string; conteggio: number; quota_pct: number }[] }[];
  serie_temporali: { column: string; periodo: string; punti: { periodo: string; conteggio: number }[] }[];
  note: string[];
};
type ScaleResult = {
  righe: number;
  colonne: number;
  dimensione: { bytes: number; leggibile: string; stimata: boolean; classe: "piccolo" | "medio" | "grande" };
  consigli: { codice: string; titolo: string; dettaglio: string; priorita: "alta" | "media" | "bassa" }[];
};
const PRIORITA_BADGE: Record<"alta" | "media" | "bassa", string> = {
  alta: "bg-danger",
  media: "bg-warning text-dark",
  bassa: "bg-secondary",
};
const CLASSE_LABEL: Record<"piccolo" | "medio" | "grande", string> = {
  piccolo: "piccolo", medio: "medio", grande: "grande",
};
const META_FIELDS: { k: keyof MetaForm; label: string; ph: string }[] = [
  { k: "titolo", label: "Titolo", ph: "Es. Popolazione residente per comune" },
  { k: "descrizione", label: "Descrizione", ph: "A cosa serve il dato, cosa contiene…" },
  { k: "licenza", label: "Licenza", ph: "Es. CC-BY-4.0" },
  { k: "ente", label: "Ente titolare", ph: "Es. Comune di Bari" },
  { k: "tema", label: "Tema EU", ph: "Es. GOVE, ECON, ENVI" },
  { k: "frequenza", label: "Frequenza aggiornamento", ph: "Es. ANNUAL, MONTHLY" },
];
type MetaForm = { titolo: string; descrizione: string; licenza: string; ente: string; tema: string; frequenza: string };

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
  const [dcat, setDcat] = useState<DcatResult | null>(null);
  const [dcatBusy, setDcatBusy] = useState(false);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [validateBusy, setValidateBusy] = useState(false);
  const [meta, setMeta] = useState<MetaForm>({ titolo: "", descrizione: "", licenza: "", ente: "", tema: "", frequenza: "" });
  const [schema, setSchema] = useState<SchemaResult | null>(null);
  const [schemaBusy, setSchemaBusy] = useState(false);
  const [tableName, setTableName] = useState("");
  const [convert, setConvert] = useState<ConvertResult | null>(null);
  const [convertBusy, setConvertBusy] = useState(false);
  const [latField, setLatField] = useState("");
  const [lonField, setLonField] = useState("");
  const [summary, setSummary] = useState<SummaryResult | null>(null);
  const [summaryBusy, setSummaryBusy] = useState(false);
  const [scale, setScale] = useState<ScaleResult | null>(null);
  const [scaleBusy, setScaleBusy] = useState(false);
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

  // Genera lo scheletro DCAT-AP_IT (POST /quality/metadata) coi campi editoriali.
  async function generaDcat() {
    const body = _body();
    if (!body) { setError("Analizza prima un file (incolla CSV/GeoJSON o un URL)."); return; }
    setDcatBusy(true);
    setError(null);
    try {
      const token = await getToken();
      const extra = Object.fromEntries(Object.entries(meta).filter(([, v]) => v.trim()));
      const res = await apiFetch("/quality/metadata", { method: "POST", token, body: JSON.stringify({ ...body, ...extra }) });
      if (!res.ok) {
        let msg = `Errore ${res.status}`;
        try { const j = await res.json(); if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg; } catch { /* */ }
        setError(msg);
        return;
      }
      setDcat((await res.json()) as DcatResult);
      setValidation(null);  // la nuova scheda invalida la validazione precedente
    } catch (e) {
      setError(`Errore di rete: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setDcatBusy(false);
    }
  }

  // Valida la scheda DCAT-AP_IT generata: campi obbligatori, licenza, FAIR.
  async function validaDcat() {
    if (!dcat) return;
    setValidateBusy(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await apiFetch("/quality/validate", { method: "POST", token, body: JSON.stringify({ metadata: dcat }) });
      if (!res.ok) {
        let msg = `Errore ${res.status}`;
        try { const j = await res.json(); if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg; } catch { /* */ }
        setError(msg);
        return;
      }
      const data = (await res.json()) as { validazione: ValidationResult };
      setValidation(data.validazione);
    } catch (e) {
      setError(`Errore di rete: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setValidateBusy(false);
    }
  }

  function scaricaDcat() {
    if (!dcat) return;
    _download(JSON.stringify(dcat, null, 2), "metadati-dcat-ap_it.json", "application/ld+json;charset=utf-8");
  }

  // Da dato a schema: inferisce schema SQL + DDL (POST /quality/schema).
  async function generaSchema() {
    const body = _body();
    if (!body) { setError("Analizza prima un CSV (incollalo o indica un URL)."); return; }
    setSchemaBusy(true);
    setError(null);
    try {
      const token = await getToken();
      const extra = tableName.trim() ? { table_name: tableName.trim() } : {};
      const res = await apiFetch("/quality/schema", { method: "POST", token, body: JSON.stringify({ ...body, ...extra }) });
      if (!res.ok) {
        let msg = `Errore ${res.status}`;
        try { const j = await res.json(); if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg; } catch { /* */ }
        setError(msg);
        return;
      }
      setSchema((await res.json()) as SchemaResult);
    } catch (e) {
      setError(`Errore di rete: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSchemaBusy(false);
    }
  }

  function scaricaSchema() {
    if (!schema) return;
    _download(schema.ddl + "\n", `${schema.table_name}.sql`, "application/sql;charset=utf-8");
  }

  // Convertitore 1-click: tabella con coordinate → GeoJSON (POST /quality/to-geojson).
  async function convertiGeoJSON() {
    const body = _body();
    if (!body) { setError("Analizza prima un file (incolla CSV/JSON o un URL)."); return; }
    setConvertBusy(true);
    setError(null);
    try {
      const token = await getToken();
      const extra = latField.trim() && lonField.trim()
        ? { lat_field: latField.trim(), lon_field: lonField.trim() }
        : {};
      const res = await apiFetch("/quality/to-geojson", { method: "POST", token, body: JSON.stringify({ ...body, ...extra }) });
      if (!res.ok) {
        let msg = `Errore ${res.status}`;
        try { const j = await res.json(); if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg; } catch { /* */ }
        setError(msg);
        return;
      }
      setConvert((await res.json()) as ConvertResult);
    } catch (e) {
      setError(`Errore di rete: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setConvertBusy(false);
    }
  }

  function scaricaGeoJSON() {
    if (!convert?.geojson) return;
    _download(JSON.stringify(convert.geojson), "dati.geojson", "application/geo+json;charset=utf-8");
  }

  // Riepiloghi pronti: statistiche, totali per categoria, andamenti (POST /quality/summary).
  async function generaSummary() {
    const body = _body();
    if (!body) { setError("Analizza prima un CSV (incollalo o indica un URL)."); return; }
    setSummaryBusy(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await apiFetch("/quality/summary", { method: "POST", token, body: JSON.stringify(body) });
      if (!res.ok) {
        let msg = `Errore ${res.status}`;
        try { const j = await res.json(); if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg; } catch { /* */ }
        setError(msg);
        return;
      }
      setSummary((await res.json()) as SummaryResult);
    } catch (e) {
      setError(`Errore di rete: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSummaryBusy(false);
    }
  }

  // Consigli di scala/performance per dataset grandi (POST /quality/scale).
  async function generaScale() {
    const body = _body();
    if (!body) { setError("Analizza prima un CSV (incollalo o indica un URL)."); return; }
    setScaleBusy(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await apiFetch("/quality/scale", { method: "POST", token, body: JSON.stringify(body) });
      if (!res.ok) {
        let msg = `Errore ${res.status}`;
        try { const j = await res.json(); if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg; } catch { /* */ }
        setError(msg);
        return;
      }
      setScale((await res.json()) as ScaleResult);
    } catch (e) {
      setError(`Errore di rete: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setScaleBusy(false);
    }
  }

  async function analizza() {
    setLoading(true);
    setError(null);
    setReport(null);
    setFixChanges(null);
    setDcat(null);
    setValidation(null);
    setSchema(null);
    setConvert(null);
    setSummary(null);
    setScale(null);
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
                onClick={() => { setText(""); setUrl(""); setReport(null); setError(null); setFixChanges(null); setDcat(null); setValidation(null); setSchema(null); setConvert(null); setSummary(null); setScale(null); }}
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

          {/* DA DATO A SCHEMA (solo CSV) */}
          {csv && (
            <div className="card shadow-sm mt-4">
              <div className="card-body">
                <h2 className="h5 mb-1">Da dato a schema (SQL)</h2>
                <p className="text-muted small">
                  Trasforma il file piatto in una tabella ben organizzata: tipi delle colonne, chiave
                  primaria e indici utili (date, codici, categorie) suggeriti dal contenuto. Ottieni il
                  comando <code>CREATE TABLE</code> pronto da eseguire.
                </p>
                <div className="d-flex flex-wrap align-items-center gap-2">
                  <input
                    className="form-control form-control-sm"
                    style={{ maxWidth: 280 }}
                    placeholder="Nome tabella (es. comuni_puglia)"
                    value={tableName}
                    onChange={(e) => setTableName(e.target.value)}
                  />
                  <button type="button" className="btn btn-outline-primary btn-sm" onClick={generaSchema} disabled={schemaBusy}>
                    {schemaBusy ? "Genero…" : "Genera schema + DDL"}
                  </button>
                </div>

                {schema && (
                  <div className="mt-3">
                    <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
                      <button type="button" className="btn btn-success btn-sm" onClick={scaricaSchema}>⬇ Scarica DDL (.sql)</button>
                      <span className="text-muted small">
                        Tabella <code>{schema.table_name}</code> · {schema.columns.length} colonne ·{" "}
                        {schema.primary_key
                          ? <>chiave primaria <code>{schema.primary_key}</code></>
                          : schema.surrogate_key ? "chiave surrogata id" : "nessuna chiave"}
                      </span>
                    </div>

                    {schema.notes.length > 0 && (
                      <div className="alert alert-warning py-2 small mb-2">
                        <ul className="mb-0">{schema.notes.map((n, i) => (<li key={i}>{n}</li>))}</ul>
                      </div>
                    )}

                    <pre className="bg-light border rounded p-2 small mb-2" style={{ maxHeight: 320, overflow: "auto" }}>
                      {schema.ddl}
                    </pre>

                    {schema.indexes.length > 0 && (
                      <div className="small">
                        <span className="fw-semibold">Indici suggeriti:</span>
                        <ul className="mb-0 mt-1">
                          {schema.indexes.map((ix) => (
                            <li key={ix.column}><code>{ix.column}</code> — {ix.reason}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* CONVERTITORE → GEOJSON (solo CSV) */}
          {csv && (
            <div className="card shadow-sm mt-4">
              <div className="card-body">
                <h2 className="h5 mb-1">Crea una mappa dal file (→ GeoJSON)</h2>
                <p className="text-muted small">
                  Se la tabella ha colonne di <strong>latitudine</strong> e <strong>longitudine</strong>,
                  le trasforma in un <strong>GeoJSON</strong> di punti pronto per la mappa e per i portali.
                  Le altre colonne diventano proprietà di ogni punto.
                </p>
                <button type="button" className="btn btn-outline-primary btn-sm" onClick={convertiGeoJSON} disabled={convertBusy}>
                  {convertBusy ? "Converto…" : "Converti in GeoJSON"}
                </button>

                {convert && !convert.ok && (
                  <div className="mt-3">
                    <div className="alert alert-warning py-2 small mb-2">{convert.error}</div>
                    {convert.candidate_columns && convert.candidate_columns.length > 0 && (
                      <div className="d-flex flex-wrap align-items-end gap-2">
                        <div>
                          <label className="form-label small mb-1">Colonna latitudine</label>
                          <select className="form-select form-select-sm" value={latField} onChange={(e) => setLatField(e.target.value)}>
                            <option value="">—</option>
                            {convert.candidate_columns.map((c) => (<option key={c} value={c}>{c}</option>))}
                          </select>
                        </div>
                        <div>
                          <label className="form-label small mb-1">Colonna longitudine</label>
                          <select className="form-select form-select-sm" value={lonField} onChange={(e) => setLonField(e.target.value)}>
                            <option value="">—</option>
                            {convert.candidate_columns.map((c) => (<option key={c} value={c}>{c}</option>))}
                          </select>
                        </div>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={convertiGeoJSON}
                          disabled={convertBusy || !latField || !lonField}
                        >
                          Riprova
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {convert && convert.ok && (
                  <div className="mt-3">
                    <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
                      <button type="button" className="btn btn-success btn-sm" onClick={scaricaGeoJSON} disabled={!convert.geojson}>
                        ⬇ Scarica GeoJSON
                      </button>
                      <span className="text-muted small">
                        {convert.n_features.toLocaleString("it-IT")} punti
                        {convert.lat_field && convert.lon_field
                          ? <> · da <code>{convert.lat_field}</code> / <code>{convert.lon_field}</code></>
                          : null}
                      </span>
                    </div>
                    {convert.warnings && convert.warnings.length > 0 && (
                      <ul className="small text-muted mb-0">
                        {convert.warnings.map((w, i) => (<li key={i}>{w}</li>))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* RIEPILOGHI PRONTI (solo CSV) */}
          {csv && (
            <div className="card shadow-sm mt-4">
              <div className="card-body">
                <h2 className="h5 mb-1">Riepiloghi pronti</h2>
                <p className="text-muted small">
                  Sintesi automatiche del contenuto: statistiche delle colonne numeriche,
                  <strong> totali per categoria</strong> e <strong>andamenti nel tempo</strong> —
                  pronti da consultare o pubblicare. Tutto calcolato sul file, nessun numero inventato.
                </p>
                <button type="button" className="btn btn-outline-primary btn-sm" onClick={generaSummary} disabled={summaryBusy}>
                  {summaryBusy ? "Calcolo…" : "Genera riepiloghi"}
                </button>

                {summary && (
                  <div className="mt-3 d-flex flex-column gap-3">
                    {summary.note.map((n, i) => (
                      <div key={i} className="alert alert-warning py-2 small mb-0">{n}</div>
                    ))}

                    {summary.numeric.length > 0 && (
                      <div>
                        <h3 className="h6 text-muted">Colonne numeriche</h3>
                        <div className="table-responsive">
                          <table className="table table-sm align-middle mb-0">
                            <thead>
                              <tr className="text-muted small text-uppercase">
                                <th>Colonna</th><th className="text-end">Conteggio</th>
                                <th className="text-end">Min</th><th className="text-end">Media</th>
                                <th className="text-end">Max</th><th className="text-end">Somma</th>
                              </tr>
                            </thead>
                            <tbody>
                              {summary.numeric.map((n) => (
                                <tr key={n.column}>
                                  <td className="fw-semibold">{n.column}</td>
                                  <td className="text-end">{n.conteggio.toLocaleString("it-IT")}</td>
                                  <td className="text-end">{n.min.toLocaleString("it-IT")}</td>
                                  <td className="text-end">{n.media.toLocaleString("it-IT")}</td>
                                  <td className="text-end">{n.max.toLocaleString("it-IT")}</td>
                                  <td className="text-end fw-semibold">{n.somma.toLocaleString("it-IT")}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {summary.categorie.map((c) => {
                      const maxC = Math.max(...c.top.map((t) => t.conteggio), 1);
                      return (
                        <div key={c.column}>
                          <h3 className="h6 text-muted mb-1">
                            Totali per <code>{c.column}</code>
                            <span className="text-muted fw-normal small"> · {c.distinti} valori{c.altri > 0 ? ` (primi ${c.top.length})` : ""}</span>
                          </h3>
                          <ul className="list-unstyled mb-0">
                            {c.top.map((t) => (
                              <li key={t.valore} className="d-flex align-items-center gap-2 small" style={{ lineHeight: 1.8 }}>
                                <span className="text-truncate" style={{ width: 160 }} title={t.valore}>{t.valore}</span>
                                <div style={{ flex: 1, height: 8, background: "#eef0f3", borderRadius: 4, maxWidth: 280 }}>
                                  <div style={{ width: `${Math.round((t.conteggio / maxC) * 100)}%`, height: "100%", borderRadius: 4, background: "#2563eb" }} />
                                </div>
                                <span style={{ width: 90, textAlign: "right" }}>
                                  {t.conteggio.toLocaleString("it-IT")} <span className="text-muted">({t.quota_pct}%)</span>
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })}

                    {summary.serie_temporali.map((s) => {
                      const maxP = Math.max(...s.punti.map((p) => p.conteggio), 1);
                      return (
                        <div key={s.column}>
                          <h3 className="h6 text-muted mb-2">Andamento nel tempo · <code>{s.column}</code> (per {s.periodo})</h3>
                          <div className="d-flex align-items-end gap-1" style={{ height: 120 }}>
                            {s.punti.map((p) => (
                              <div key={p.periodo} className="text-center" style={{ flex: 1, minWidth: 24 }} title={`${p.periodo}: ${p.conteggio}`}>
                                <div
                                  style={{
                                    height: `${Math.round((p.conteggio / maxP) * 96)}px`,
                                    background: "#2563eb",
                                    borderRadius: "3px 3px 0 0",
                                  }}
                                />
                                <div className="text-muted" style={{ fontSize: 10, marginTop: 2 }}>{p.periodo}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* VELOCE ANCHE QUANDO È GRANDE (solo CSV) */}
          {csv && (
            <div className="card shadow-sm mt-4">
              <div className="card-body">
                <h2 className="h5 mb-1">Veloce anche quando è grande</h2>
                <p className="text-muted small">
                  In base alla dimensione e al contenuto del file, suggerisce come tenerlo veloce
                  da consultare anche con molti dati: formato compresso, indici, suddivisione e
                  modalità di pubblicazione.
                </p>
                <button type="button" className="btn btn-outline-primary btn-sm" onClick={generaScale} disabled={scaleBusy}>
                  {scaleBusy ? "Valuto…" : "Valuta scala e performance"}
                </button>

                {scale && (
                  <div className="mt-3">
                    <p className="small mb-2">
                      <span className="text-muted">Dimensione:</span>{" "}
                      <strong>{scale.dimensione.leggibile}</strong>
                      {scale.dimensione.stimata ? " (stimata)" : ""} ·{" "}
                      {scale.righe.toLocaleString("it-IT")} righe × {scale.colonne} colonne ·{" "}
                      <span className="badge bg-light text-dark border align-middle">
                        dataset {CLASSE_LABEL[scale.dimensione.classe]}
                      </span>
                    </p>
                    <ul className="list-group list-group-flush">
                      {scale.consigli.map((c) => (
                        <li key={c.codice} className="list-group-item px-0">
                          <div className="d-flex gap-2 align-items-start">
                            <span className={`badge ${PRIORITA_BADGE[c.priorita]} flex-shrink-0`} style={{ minWidth: 64 }}>
                              {c.priorita}
                            </span>
                            <div>
                              <div className="fw-semibold">{c.titolo}</div>
                              <div className="small text-muted">{c.dettaglio}</div>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* SCHEDA DCAT-AP_IT */}
          <div className="card shadow-sm mt-4">
            <div className="card-body">
              <h2 className="h5 mb-1">Scheda descrittiva (DCAT-AP_IT)</h2>
              <p className="text-muted small">
                Genera i metadati pronti per il portale: formato, schema dei campi e keyword sono
                ricavati dal file; compila i campi editoriali (o lasciali da completare).
              </p>
              <div className="row g-2">
                {META_FIELDS.map((f) => (
                  <div className={f.k === "descrizione" ? "col-12" : "col-md-6"} key={f.k}>
                    <input
                      className="form-control form-control-sm"
                      placeholder={`${f.label} — ${f.ph}`}
                      value={meta[f.k]}
                      onChange={(e) => setMeta((m) => ({ ...m, [f.k]: e.target.value }))}
                    />
                  </div>
                ))}
              </div>
              <button type="button" className="btn btn-outline-primary btn-sm mt-3" onClick={generaDcat} disabled={dcatBusy}>
                {dcatBusy ? "Genero…" : "Genera scheda DCAT-AP_IT"}
              </button>

              {dcat && (
                <div className="mt-3">
                  {dcat.campi_mancanti.length > 0 && (
                    <div className="alert alert-warning py-2">
                      <strong>Da completare prima di pubblicare:</strong>
                      <ul className="mb-0 mt-1 small">
                        {dcat.campi_mancanti.map((c) => (<li key={c}>{c}</li>))}
                      </ul>
                    </div>
                  )}
                  <div className="d-flex align-items-center gap-2 mb-2 flex-wrap">
                    <button type="button" className="btn btn-success btn-sm" onClick={scaricaDcat}>⬇ Scarica metadati (JSON-LD)</button>
                    <button type="button" className="btn btn-outline-primary btn-sm" onClick={validaDcat} disabled={validateBusy}>
                      {validateBusy ? "Valido…" : "Valida (DCAT-AP_IT + FAIR)"}
                    </button>
                    <span className="text-muted small">{dcat.schema_campi.length} campi nello schema</span>
                  </div>

                  {validation && (
                    <div className="border rounded p-3 mb-2">
                      <div className="d-flex align-items-center gap-2 mb-2 flex-wrap">
                        <span className={`badge ${validation.valido ? "bg-success" : "bg-danger"}`}>
                          {validation.valido ? "Conforme" : "Non ancora conforme"}
                        </span>
                        <span className="small">
                          Licenza:{" "}
                          {validation.licenza.aperta === true
                            ? <span className="text-success">aperta ({validation.licenza.dichiarata})</span>
                            : validation.licenza.aperta === false
                              ? <span className="text-danger">non aperta ({validation.licenza.dichiarata}) → usa {validation.licenza.suggerita}</span>
                              : <span className="text-muted">non indicata → suggerita {validation.licenza.suggerita}</span>}
                        </span>
                      </div>

                      <div className="row g-2 text-center mb-2">
                        {([
                          ["Trovabile", validation.fair.findable],
                          ["Accessibile", validation.fair.accessible],
                          ["Interoperabile", validation.fair.interoperable],
                          ["Riutilizzabile", validation.fair.reusable],
                          ["FAIR", validation.fair.overall],
                        ] as [string, number][]).map(([label, val]) => (
                          <div className="col" key={label}>
                            <div className={`h5 mb-0 ${scoreColor(val)}`}>{val}</div>
                            <div className="small text-muted">{label}</div>
                          </div>
                        ))}
                      </div>

                      {validation.findings.length > 0 && (
                        <ul className="list-group list-group-flush">
                          {validation.findings.map((f) => (
                            <li key={f.codice} className="list-group-item px-0 py-1 d-flex gap-2 align-items-start border-0">
                              <span className={`badge ${LIVELLO[f.livello].badge} flex-shrink-0`} style={{ minWidth: 96 }}>
                                {LIVELLO[f.livello].label}
                              </span>
                              <span className="small">{f.messaggio} <span className="text-muted">— <code>{f.campo}</code></span></span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  <pre className="bg-light border rounded p-2 small mb-0" style={{ maxHeight: 320, overflow: "auto" }}>
                    {JSON.stringify(dcat.dataset, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
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
