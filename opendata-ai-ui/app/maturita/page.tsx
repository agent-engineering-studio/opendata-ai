"use client";

import { Suspense, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { DashboardGate } from "@/components/DashboardGate";

/*
 * Stato della maturità open data: ranking degli enti + scorecard, con export
 * CSV (backend) e PDF (pdfmake lato client). Anello valore⇄maturità: mostra la
 * domanda di riuso non soddisfatta.
 */

type Dimensions = { policy: number; portal: number; quality: number; impact: number };
type RankItem = { entity: { id: number; name: string }; overall: number; level: string };
type Scorecard = {
  entity: { id: number; name: string };
  level: string;
  overall: number;
  dimensions: Dimensions;
  recommendations: { code: string; message: string }[];
  unmet_reuse_demand?: { count: number; items: string[] };
};

function Bar({ label, v }: { label: string; v: number }) {
  return (
    <div className="d-flex align-items-center gap-2 mb-1" style={{ fontSize: 13 }}>
      <span style={{ width: 90 }}>{label}</span>
      <div style={{ flex: 1, background: "#e2e8f0", borderRadius: 4, height: 14 }}>
        <div style={{ width: `${Math.max(0, Math.min(100, v))}%`, background: "#2563eb", height: 14, borderRadius: 4 }} />
      </div>
      <span style={{ width: 44, textAlign: "right" }}>{v.toFixed(0)}</span>
    </div>
  );
}

function MaturitaInner() {
  const { getToken } = useAuth();
  const [ranking, setRanking] = useState<RankItem[]>([]);
  const [sc, setSc] = useState<Scorecard | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        const r = await apiFetch("/maturity/ranking", { token });
        if (r.ok) setRanking(((await r.json()).ranking ?? []) as RankItem[]);
      } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function openScorecard(id: number) {
    setErr(null);
    try {
      const token = await getToken();
      const r = await apiFetch(`/maturity/entities/${id}`, { token });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSc((await r.json()) as Scorecard);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }

  async function exportCsv(id: number) {
    const token = await getToken();
    const r = await apiFetch(`/maturity/entities/${id}/scorecard.csv`, { token });
    if (!r.ok) { setErr(`CSV HTTP ${r.status}`); return; }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `scorecard-${id}.csv`; a.click();
    URL.revokeObjectURL(url);
  }

  async function exportPdf(card: Scorecard) {
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const pdfMakeModule = await import("pdfmake/build/pdfmake");
    const pdfFontsModule = await import("pdfmake/build/vfs_fonts");
    const pdfMake: any = (pdfMakeModule as any).default ?? pdfMakeModule;
    const fonts: any = pdfFontsModule as any;
    pdfMake.vfs = fonts.pdfMake?.vfs ?? fonts.default?.pdfMake?.vfs ?? fonts.vfs ?? fonts.default?.vfs ?? pdfMake.vfs;
    /* eslint-enable @typescript-eslint/no-explicit-any */
    const d = card.dimensions;
    pdfMake.createPdf({
      content: [
        { text: `Scorecard maturità — ${card.entity.name}`, style: "h" },
        { text: `Livello: ${card.level} (${card.overall}/100)`, margin: [0, 4, 0, 8] },
        { ul: [
          `Policy: ${d.policy}`, `Portale: ${d.portal}`, `Qualità: ${d.quality}`, `Impatto: ${d.impact}`,
        ] },
        { text: "Raccomandazioni", style: "h2", margin: [0, 8, 0, 4] },
        { ul: card.recommendations.map((r) => r.message) },
        ...(card.unmet_reuse_demand?.count
          ? [{ text: "Domanda di riuso non soddisfatta", style: "h2", margin: [0, 8, 0, 4] },
             { ul: card.unmet_reuse_demand.items }]
          : []),
      ],
      styles: { h: { fontSize: 16, bold: true }, h2: { fontSize: 12, bold: true } },
    }).download(`scorecard-${card.entity.id}.pdf`);
  }

  return (
    <main id="main-content" className="container py-4">
      <h1 className="h3 mb-1">Stato della maturità open data</h1>
      <p className="text-slate-500 mb-3" style={{ fontSize: 14 }}>
        Classifica degli enti per maturità (ODM 2025) e scorecard esportabile.
      </p>
      {err ? <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700 mb-3" style={{ fontSize: 14 }}>{err}</div> : null}

      <div className="row g-4">
        <div className="col-md-5">
          <h2 className="h6 text-slate-500">Classifica</h2>
          <table className="table table-sm" style={{ fontSize: 14 }}>
            <thead><tr><th>Ente</th><th>Livello</th><th>Overall</th></tr></thead>
            <tbody>
              {ranking.map((r) => (
                <tr key={r.entity.id} style={{ cursor: "pointer" }} onClick={() => openScorecard(r.entity.id)}>
                  <td>{r.entity.name}</td><td>{r.level}</td><td>{r.overall.toFixed(0)}</td>
                </tr>
              ))}
              {ranking.length === 0 ? <tr><td colSpan={3} className="text-slate-400">Nessun ente valutato.</td></tr> : null}
            </tbody>
          </table>
        </div>

        <div className="col-md-7">
          {sc ? (
            <>
              <div className="d-flex justify-content-between align-items-center">
                <h2 className="h5 mb-0">{sc.entity.name}</h2>
                <span className="badge bg-primary">{sc.level} · {sc.overall.toFixed(0)}/100</span>
              </div>
              <div className="my-3">
                <Bar label="Policy" v={sc.dimensions.policy} />
                <Bar label="Portale" v={sc.dimensions.portal} />
                <Bar label="Qualità" v={sc.dimensions.quality} />
                <Bar label="Impatto" v={sc.dimensions.impact} />
              </div>
              {sc.unmet_reuse_demand?.count ? (
                <div className="mb-2" style={{ fontSize: 13 }}>
                  <strong>Domanda di riuso non soddisfatta ({sc.unmet_reuse_demand.count}):</strong>
                  <ul className="mb-0">{sc.unmet_reuse_demand.items.map((g, i) => <li key={i}>{g}</li>)}</ul>
                </div>
              ) : null}
              <div className="d-flex gap-2">
                <button className="btn btn-sm btn-outline-primary" onClick={() => exportCsv(sc.entity.id)}>Esporta CSV</button>
                <button className="btn btn-sm btn-outline-secondary" onClick={() => exportPdf(sc)}>Esporta PDF</button>
              </div>
            </>
          ) : (
            <p className="text-slate-500" style={{ fontSize: 14 }}>Seleziona un ente dalla classifica.</p>
          )}
        </div>
      </div>
    </main>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <Suspense fallback={<div className="container py-4 text-slate-500">Caricamento…</div>}>
        <MaturitaInner />
      </Suspense>
    </DashboardGate>
  );
}
