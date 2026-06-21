"use client";

import { useRef, useState } from "react";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DashboardGate } from "@/components/DashboardGate";

// ─── tipi del report restituito da POST /quality/profile ───
type Finding = { livello: "alto" | "medio" | "basso"; codice: string; messaggio: string; colonna?: string };
type ColonnaProfilo = {
  nome: string;
  tipo: string;
  vuoti_pct: number;
  distinti: number;
  esempi: string[];
  problemi: string[];
};
type Report = {
  format: string;
  righe: number;
  colonne: number;
  separatore: string | null;
  righe_profilate?: number;
  colonne_profilo: ColonnaProfilo[];
  findings: Finding[];
  punteggio: number;
};

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
  const fileRef = useRef<HTMLInputElement | null>(null);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      setText(String(reader.result ?? ""));
      setUrl("");
    };
    reader.readAsText(f);
  }

  async function analizza() {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const body = text.trim() ? { content: text } : url.trim() ? { url: url.trim() } : null;
      if (!body) {
        setError("Incolla un CSV, carica un file oppure indica un URL.");
        return;
      }
      const token = await getToken();
      const res = await apiFetch("/quality/profile", {
        method: "POST",
        token,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        let msg = `Errore ${res.status}`;
        try {
          const j = await res.json();
          if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg;
        } catch {
          /* ignore */
        }
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

  return (
    <div className="container py-4" style={{ maxWidth: 980 }}>
      <h1 className="h3 mb-1">Qualità dei dati</h1>
      <p className="text-muted">
        Incolla un CSV (o caricane il file, o indica un URL pubblico) e ricevi una
        diagnosi automatica: tipo delle colonne, valori mancanti, problemi e un
        punteggio di qualità. Tutto deterministico, nessun dato inventato.
      </p>

      {/* INPUT */}
      <div className="card shadow-sm mb-4">
        <div className="card-body">
          <label className="form-label fw-semibold" htmlFor="csv">Contenuto CSV</label>
          <textarea
            id="csv"
            className="form-control font-monospace"
            style={{ minHeight: 160, fontSize: ".85rem" }}
            placeholder="comune,popolazione,data&#10;Bari,320475,2023-01-01"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="d-flex flex-wrap align-items-center gap-2 mt-2">
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => fileRef.current?.click()}>
              Carica file…
            </button>
            <input ref={fileRef} type="file" accept=".csv,.tsv,.txt,text/csv" className="d-none" onChange={onFile} />
            <button type="button" className="btn btn-sm btn-link text-muted" onClick={() => { setText(ESEMPIO_CSV); setUrl(""); }}>
              Usa un esempio
            </button>
            <span className="text-muted small ms-auto">oppure</span>
          </div>
          <input
            type="url"
            className="form-control mt-2"
            placeholder="https://… (URL pubblico di un CSV)"
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
                onClick={() => { setText(""); setUrl(""); setReport(null); setError(null); }}
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
              <ul className="list-unstyled mb-0 small text-muted">
                <li><strong>{report.righe.toLocaleString("it-IT")}</strong> righe · <strong>{report.colonne}</strong> colonne</li>
                <li>Separatore rilevato: <code>{report.separatore === "\t" ? "\\t (tab)" : report.separatore}</code></li>
                <li>{report.findings.length} segnalazion{report.findings.length === 1 ? "e" : "i"}</li>
              </ul>
            </div>
          </div>

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
                    {report.colonne_profilo.map((c) => (
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
