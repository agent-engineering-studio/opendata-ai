"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DashboardGate } from "@/components/DashboardGate";

/*
 * Copilota Open Data per l'ente (#170/#222): accompagnamento attivo dal "zero dati"
 * a una politica open data viva. Dato un codice ISTAT, mostra la diagnosi + lo
 * STATO (zero→maturo, #184) con il percorso ente-specifico, il piano prioritizzato
 * (valore×sforzo) e la bozza di Politica generata. Tutto via /dataplan/{istat}/*.
 */

type PercorsoStep = { chiave: string; titolo: string; descrizione: string; endpoint: string | null };
type Diagnosi = {
  istat: string;
  comune: string;
  pubblicato: { n_dataset: number; overall: number; level: string } | null;
  hint: string | null;
  gia_aperto_nazionale: { id: string; nome: string; fonte: string }[];
  accompagnamento: {
    stato: string; etichetta: string; descrizione: string;
    prossima_azione: string; percorso: PercorsoStep[];
  };
};
type RankedVoce = {
  candidate: { id: string; nome: string; area: string; privacy: string };
  valore: number; sforzo: number; quadrante: string; motivazione: string;
};
type Piano = { ente: string; ranking: RankedVoce[]; piano: { quick_win: string[] } };
type Politica = { titolo: string; licenza: string; generato_con: string;
                  sezioni: { titolo: string; testo: string }[] };

const STATO_BADGE: Record<string, string> = {
  zero_dati: "bg-danger-subtle text-danger-emphasis border-danger-subtle",
  pochi_dati: "bg-warning-subtle text-warning-emphasis border-warning-subtle",
  in_crescita: "bg-primary-subtle text-primary-emphasis border-primary-subtle",
  maturo: "bg-success-subtle text-success-emphasis border-success-subtle",
};
const QUAD_LABEL: Record<string, string> = {
  quick_win: "Quick win", strategico: "Strategico",
  riempitivo: "Riempitivo", basso_valore: "Bassa priorità",
};

function CopilotaInner() {
  const { getToken } = useAuth();
  const [istat, setIstat] = useState("");
  const [diag, setDiag] = useState<Diagnosi | null>(null);
  const [piano, setPiano] = useState<Piano | null>(null);
  const [politica, setPolitica] = useState<Politica | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function call<T>(method: string, path: string, body?: object): Promise<T> {
    const token = await getToken();
    const res = await apiFetch(path, {
      token, method, ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
    return res.json();
  }

  async function runDiagnosi(code: string) {
    if (!/^\d{6}$/.test(code)) { setErr("Inserisci un codice ISTAT di 6 cifre (es. 072021)."); return; }
    setErr(null); setPiano(null); setPolitica(null); setBusy("diagnosi");
    try {
      setDiag(await call<Diagnosi>("GET", `/dataplan/${code}/diagnosi`));
    } catch (e2) { setErr(String((e2 as Error).message)); setDiag(null); }
    finally { setBusy(null); }
  }

  async function diagnostica(e: React.FormEvent) {
    e.preventDefault();
    await runDiagnosi(istat.trim());
  }

  // Drill-down dal cruscotto regionale: /copilota#<istat> precompila e avvia.
  useEffect(() => {
    const h = typeof window !== "undefined" ? window.location.hash.slice(1) : "";
    if (/^\d{6}$/.test(h)) {
      setIstat(h);
      void runDiagnosi(h);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function mostraPiano() {
    if (!diag) return;
    setBusy("piano");
    try { setPiano(await call<Piano>("GET", `/dataplan/${diag.istat}/piano`)); }
    catch (e2) { setErr(String((e2 as Error).message)); }
    finally { setBusy(null); }
  }

  async function generaPolitica() {
    if (!diag) return;
    setBusy("politica");
    try { setPolitica(await call<Politica>("POST", `/dataplan/${diag.istat}/politica`, {})); }
    catch (e2) { setErr(String((e2 as Error).message)); }
    finally { setBusy(null); }
  }

  return (
    <main className="container py-4" style={{ maxWidth: 960 }}>
      <h1 className="h3 mb-1">Copilota Open Data</h1>
      <p className="text-muted">
        Dal <strong>&laquo;zero dati&raquo;</strong> a una politica open data viva. Inserisci il
        codice ISTAT del comune: il Copilota fotografa quanto sei aperto oggi, riconosce lo{" "}
        <strong>stato dell&apos;ente</strong> e propone un <strong>percorso su misura</strong> —
        cosa aprire prima (per valore/sforzo), la bozza di Politica e le istruzioni per gli uffici.
        Gli open data restano l&apos;unica fonte ufficiale: il Copilota accompagna, non conserva i dati.
      </p>

      <form className="row g-2 align-items-end mb-4" onSubmit={diagnostica}>
        <div className="col-auto">
          <label className="form-label small mb-1" htmlFor="istat">Codice ISTAT del comune</label>
          <input id="istat" className="form-control" style={{ maxWidth: 220 }} value={istat}
                 onChange={(e) => setIstat(e.target.value)} placeholder="es. 072021" inputMode="numeric" />
        </div>
        <div className="col-auto">
          <button className="btn btn-primary" type="submit" disabled={busy !== null}>
            {busy === "diagnosi" ? "Analisi…" : "Diagnosi"}
          </button>
        </div>
      </form>

      {err ? <div className="alert alert-warning">{err}</div> : null}

      {diag ? (
        <>
          <div className="card shadow-sm mb-4">
            <div className="card-body">
              <div className="d-flex align-items-center gap-2 mb-2">
                <h2 className="h5 mb-0">{diag.comune}</h2>
                <span className={`badge rounded-pill border ${STATO_BADGE[diag.accompagnamento.stato] || ""}`}>
                  {diag.accompagnamento.etichetta}
                </span>
              </div>
              <p className="text-muted mb-2">{diag.accompagnamento.descrizione}</p>
              {diag.pubblicato ? (
                <p className="small mb-2">
                  Oggi: <strong>{diag.pubblicato.n_dataset}</strong> dataset sul portale ·
                  maturità <strong>{Math.round(diag.pubblicato.overall)}/100</strong> ({diag.pubblicato.level}).
                </p>
              ) : (
                <p className="small text-muted mb-2">{diag.hint}</p>
              )}
              <p className="mb-3"><strong>Prossima azione.</strong> {diag.accompagnamento.prossima_azione}</p>

              <h3 className="h6">Percorso consigliato</h3>
              <ol className="mb-0">
                {diag.accompagnamento.percorso.map((s) => (
                  <li key={s.chiave} className="mb-1">
                    <strong>{s.titolo}</strong> — <span className="text-muted">{s.descrizione}</span>
                  </li>
                ))}
              </ol>

              {diag.gia_aperto_nazionale.length ? (
                <div className="mt-3">
                  <h3 className="h6">Già aperto a livello nazionale (basta linkarlo)</h3>
                  <ul className="small mb-0">
                    {diag.gia_aperto_nazionale.map((g) => (
                      <li key={g.id}>{g.nome} — <span className="text-muted">{g.fonte}</span></li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </div>

          <div className="d-flex gap-2 mb-4">
            <button className="btn btn-outline-primary" onClick={mostraPiano} disabled={busy !== null}>
              {busy === "piano" ? "…" : "Mostra il piano prioritizzato"}
            </button>
            <button className="btn btn-outline-secondary" onClick={generaPolitica} disabled={busy !== null}>
              {busy === "politica" ? "…" : "Genera bozza di Politica"}
            </button>
          </div>
        </>
      ) : null}

      {piano ? (
        <div className="card shadow-sm mb-4">
          <div className="card-body">
            <h2 className="h5 mb-3">Piano prioritizzato — {piano.ente}</h2>
            <div className="table-responsive">
              <table className="table table-sm align-middle">
                <thead><tr><th>Priorità</th><th>Dataset</th><th>Area</th><th>Valore</th><th>Sforzo</th></tr></thead>
                <tbody>
                  {piano.ranking.map((r) => (
                    <tr key={r.candidate.id}>
                      <td><span className="badge bg-light text-dark border">{QUAD_LABEL[r.quadrante] || r.quadrante}</span></td>
                      <td>{r.candidate.nome}</td>
                      <td className="text-muted">{r.candidate.area}</td>
                      <td>{r.valore}/100</td>
                      <td>{r.sforzo}/4</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}

      {politica ? (
        <div className="card shadow-sm mb-4">
          <div className="card-body">
            <h2 className="h5 mb-1">{politica.titolo}</h2>
            <p className="small text-muted mb-3">
              Licenza {politica.licenza} · generata {politica.generato_con === "llm" ? "con AI" : "in modalità offline"}.
            </p>
            {politica.sezioni.map((s) => (
              <div key={s.titolo} className="mb-2">
                <h3 className="h6 mb-1">{s.titolo}</h3>
                <p className="small mb-0">{s.testo}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default function CopilotaPage() {
  return (
    <DashboardGate>
      <CopilotaInner />
    </DashboardGate>
  );
}
