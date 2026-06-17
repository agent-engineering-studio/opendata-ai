"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { apiFetch, apiUrl } from "@/lib/api";
import { DashboardGate } from "@/components/DashboardGate";

/*
 * Sito civico: crea snapshot versionati, anteprima delle pagine statiche generate
 * dal backend (HTML self-contained) ed esporta il bundle zip pubblicabile.
 */

const PAGES = [
  ["index.html", "Stato dell'arte"],
  ["investimenti.html", "Investimenti"],
  ["opportunita.html", "Opportunità"],
  ["rischi.html", "Rischi"],
  ["avanzamento.html", "Avanzamento"],
  ["mappa.html", "Mappa"],
  ["scorecard.html", "Maturità"],
  ["community.html", "Community"],
];

function SitoInner() {
  const { getToken } = useAuth();
  const params = useSearchParams();
  const [istat, setIstat] = useState(params.get("istat") ?? "072021");
  const [snapId, setSnapId] = useState("2026-H1");
  const [page, setPage] = useState("index.html");
  const [html, setHtml] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function createSnapshot() {
    setBusy(true); setMsg(null);
    try {
      const token = await getToken();
      const r = await apiFetch(`/territory/${istat.trim()}/snapshot`, {
        method: "POST", token, body: JSON.stringify({ snapshot_id: snapId.trim() }),
      });
      if (r.status === 409) { setMsg(`Snapshot ${snapId} già esistente (non si sovrascrive).`); return; }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setMsg(`Snapshot ${data.snapshot_id} creato.` + (data.checkin ? ` Check-in: ${data.checkin.summary}` : ""));
    } catch (e) {
      setMsg("Errore: " + (e instanceof Error ? e.message : String(e)));
    } finally { setBusy(false); }
  }

  async function preview() {
    setBusy(true); setMsg(null); setHtml(null);
    try {
      const token = await getToken();
      const r = await apiFetch(`/territory/${istat.trim()}/site/preview?page=${page}`, { token });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setHtml(await r.text());
    } catch (e) {
      setMsg("Errore anteprima: " + (e instanceof Error ? e.message : String(e)));
    } finally { setBusy(false); }
  }

  async function exportZip() {
    setBusy(true); setMsg(null);
    try {
      const token = await getToken();
      const r = await apiFetch(`/territory/${istat.trim()}/site/export`, { method: "POST", token });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `sito-civico-${istat.trim()}.zip`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setMsg("Errore export: " + (e instanceof Error ? e.message : String(e)));
    } finally { setBusy(false); }
  }

  return (
    <main id="main-content" className="container py-4">
      <h1 className="h3 mb-1">Sito civico</h1>
      <p className="text-slate-500 mb-3" style={{ fontSize: 14 }}>
        Genera snapshot versionati e pubblica un sito statico self-contained del comune
        (stato dell&apos;arte, investimenti, opportunità, rischi, avanzamento, community).
      </p>

      <div className="d-flex flex-wrap gap-2 mb-3" style={{ maxWidth: 720 }}>
        <input className="form-control" style={{ width: 160 }} placeholder="ISTAT"
          value={istat} onChange={(e) => setIstat(e.target.value)} />
        <input className="form-control" style={{ width: 140 }} placeholder="snapshot (2026-H1)"
          value={snapId} onChange={(e) => setSnapId(e.target.value)} />
        <button className="btn btn-outline-primary" onClick={createSnapshot} disabled={busy}>Crea snapshot</button>
        <select className="form-select" style={{ width: 180 }} value={page} onChange={(e) => setPage(e.target.value)}>
          {PAGES.map(([f, t]) => <option key={f} value={f}>{t}</option>)}
        </select>
        <button className="btn btn-primary" onClick={preview} disabled={busy}>Anteprima</button>
        <button className="btn btn-success" onClick={exportZip} disabled={busy}>Esporta ZIP</button>
      </div>

      {msg ? <div className="rounded border bg-light px-3 py-2 mb-3" style={{ fontSize: 14 }}>{msg}</div> : null}

      {html ? (
        <iframe title="anteprima sito civico" srcDoc={html}
          style={{ width: "100%", height: 600, border: "1px solid #e2e8f0", borderRadius: 6 }} />
      ) : (
        <p className="text-slate-500" style={{ fontSize: 14 }}>
          Crea almeno uno snapshot, poi premi Anteprima. (Endpoint backend: {apiUrl(`/territory/${istat}/site/preview`)})
        </p>
      )}
    </main>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <Suspense fallback={<div className="container py-4 text-slate-500">Caricamento…</div>}>
        <SitoInner />
      </Suspense>
    </DashboardGate>
  );
}
