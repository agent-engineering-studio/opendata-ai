"use client";

import { useEffect, useRef, useState } from "react";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DashboardGate } from "@/components/DashboardGate";
import { AssistantMarkdown } from "@/components/AssistantMarkdown";

// ─── tipi allineati a opendata_backend.ideas.models ───
type Area = "salute" | "ambiente" | "territorio" | "turismo";
type ChatMessage = { role: "user" | "assistant"; content: string };
type IdeaDataset = {
  id: string; title: string; url: string; formats: string[];
  stars: number; license_open: boolean; quality_note: string; modified?: string | null;
};
type FundingProject = {
  clp: string; titolo: string; ciclo?: string | null; stato?: string | null;
  finanziamento_totale?: number | null; url?: string | null;
};
type ChatResponse = {
  reply: string; stage: string; stage_label: string;
  datasets: IdeaDataset[]; funding: FundingProject[];
  suggestions: string[]; report_ready: boolean; offline: boolean;
};
type ReportResponse = {
  report_md: string; idea_id: string; titolo: string; generato_il: string; offline: boolean;
};

const AREAS: { id: Area; label: string; emoji: string }[] = [
  { id: "salute", label: "Salute", emoji: "🩺" },
  { id: "ambiente", label: "Ambiente", emoji: "🌿" },
  { id: "territorio", label: "Territorio", emoji: "🏘️" },
  { id: "turismo", label: "Turismo", emoji: "🧭" },
];

const STAGES = [
  { id: "inquadramento", label: "Inquadra la sfida" },
  { id: "esplorazione", label: "Esplora i dati" },
  { id: "divergenza", label: "Genera idee" },
  { id: "convergenza", label: "Scegli e critica" },
  { id: "sintesi", label: "Scheda finale" },
];

function euro(v?: number | null): string {
  if (!v) return "n/d";
  return v.toLocaleString("it-IT", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

export default function IdeeLabPage() {
  const { getToken } = useAuth();
  const [area, setArea] = useState<Area | null>(null);
  const [territory, setTerritory] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [stage, setStage] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<IdeaDataset[]>([]);
  const [funding, setFunding] = useState<FundingProject[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [reportReady, setReportReady] = useState(false);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, report]);

  async function sendMessage(text: string) {
    if (!text.trim() || !area || loading) return;
    setError(null);
    const next: ChatMessage[] = [...messages, { role: "user", content: text.trim() }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const token = await getToken();
      const res = await apiFetch("/ideas/chat", {
        method: "POST",
        token,
        body: JSON.stringify({
          messages: next, area, territory: territory || null, stage,
          datasets: datasets.length ? datasets : null,
          funding: funding.length ? funding : null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ChatResponse = await res.json();
      setMessages([...next, { role: "assistant", content: data.reply }]);
      setStage(data.stage);
      setDatasets(data.datasets);
      setFunding(data.funding);
      setSuggestions(data.suggestions);
      setReportReady(data.report_ready);
    } catch (e) {
      setError(`Non sono riuscito a rispondere: ${e instanceof Error ? e.message : e}. Riprova.`);
      setMessages(messages);
    } finally {
      setLoading(false);
    }
  }

  async function generateReport() {
    if (!area || loading) return;
    setError(null);
    setLoading(true);
    try {
      const token = await getToken();
      const res = await apiFetch("/ideas/report", {
        method: "POST",
        token,
        body: JSON.stringify({
          messages, area, territory: territory || null,
          datasets: datasets.length ? datasets : null,
          funding: funding.length ? funding : null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setReport(await res.json());
    } catch (e) {
      setError(`Generazione scheda fallita: ${e instanceof Error ? e.message : e}. Riprova.`);
    } finally {
      setLoading(false);
    }
  }

  function downloadReport() {
    if (!report) return;
    const blob = new Blob([report.report_md], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${report.idea_id}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function restart() {
    setMessages([]); setStage(null); setDatasets([]); setFunding([]);
    setSuggestions([]); setReportReady(false); setReport(null); setError(null);
  }

  const stageIndex = stage ? STAGES.findIndex((s) => s.id === stage) : -1;

  return (
    <DashboardGate>
      <main className="container py-4">
        <header className="mb-4">
          <h1 className="h3 mb-1">Idea Lab</h1>
          <p className="text-muted mb-0">
            Un percorso guidato di brainstorming: dai dati aperti della Puglia a
            un&apos;idea progettuale concreta, con evidenza, finanziabilità e kit
            per il team di sviluppo.
          </p>
        </header>

        {/* Stepper del percorso */}
        <div className="card shadow-sm mb-4">
          <div className="card-body d-flex flex-wrap gap-2 align-items-center">
            {STAGES.map((s, i) => (
              <span
                key={s.id}
                className={`badge rounded-pill ${
                  i === stageIndex ? "bg-primary" : i < stageIndex ? "bg-success" : "bg-secondary"
                }`}
              >
                {i + 1}. {s.label}
              </span>
            ))}
            {messages.length > 0 && (
              <button className="btn btn-sm btn-outline-secondary ms-auto" onClick={restart}>
                Ricomincia
              </button>
            )}
          </div>
        </div>

        {/* Setup iniziale: area + territorio */}
        {messages.length === 0 && !report && (
          <div className="card shadow-sm mb-4">
            <div className="card-body">
              <h2 className="h5">Da dove partiamo?</h2>
              <p className="text-muted">Scegli l&apos;area della tua sfida:</p>
              <div className="d-flex flex-wrap gap-2 mb-3">
                {AREAS.map((a) => (
                  <button
                    key={a.id}
                    className={`btn ${area === a.id ? "btn-primary" : "btn-outline-primary"}`}
                    onClick={() => setArea(a.id)}
                  >
                    {a.emoji} {a.label}
                  </button>
                ))}
              </div>
              <label className="form-label" htmlFor="territorio-input">
                Territorio (facoltativo)
              </label>
              <input
                id="territorio-input"
                className="form-control mb-3"
                style={{ maxWidth: 420 }}
                placeholder="es. Gioia del Colle, provincia di Bari…"
                value={territory}
                onChange={(e) => setTerritory(e.target.value)}
              />
              <p className="text-muted mb-0">
                Poi descrivi la sfida nella casella qui sotto: il percorso si adatta
                alle tue risposte, una domanda alla volta.
              </p>
            </div>
          </div>
        )}

        <div className="row g-4">
          {/* Colonna chat */}
          <div className="col-lg-8">
            <div className="card shadow-sm mb-3">
              <div className="card-body" style={{ minHeight: 260 }}>
                {messages.length === 0 && (
                  <p className="text-muted mb-0">
                    {area
                      ? "Descrivi la tua sfida per iniziare il percorso."
                      : "Scegli prima un'area tematica."}
                  </p>
                )}
                {messages.map((m, i) =>
                  m.role === "user" ? (
                    <p key={i} className="text-end">
                      <span className="badge bg-light text-dark border fs-6 fw-normal text-wrap text-start">
                        {m.content}
                      </span>
                    </p>
                  ) : (
                    <div key={i} className="mb-3">
                      <AssistantMarkdown text={m.content} />
                    </div>
                  ),
                )}
                {loading && <p className="text-muted fst-italic">Sto ragionando sui dati…</p>}
                {error && <div className="alert alert-warning py-2">{error}</div>}
                <div ref={bottomRef} />
              </div>
            </div>

            {/* Suggerimenti rapidi */}
            {suggestions.length > 0 && !report && (
              <div className="d-flex flex-wrap gap-2 mb-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    className="btn btn-sm btn-outline-secondary"
                    disabled={loading}
                    onClick={() => sendMessage(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {/* Input */}
            {!report && (
              <form
                className="d-flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  void sendMessage(input);
                }}
              >
                <input
                  className="form-control"
                  placeholder={area ? "Scrivi qui…" : "Scegli prima un'area"}
                  value={input}
                  disabled={!area || loading}
                  onChange={(e) => setInput(e.target.value)}
                />
                <button className="btn btn-primary" type="submit" disabled={!area || loading}>
                  Invia
                </button>
              </form>
            )}

            {/* Scheda finale */}
            {reportReady && !report && (
              <div className="alert alert-success d-flex align-items-center justify-content-between mt-3">
                <span>Il percorso è completo: genera la scheda progetto.</span>
                <button className="btn btn-success" disabled={loading} onClick={generateReport}>
                  Genera la scheda
                </button>
              </div>
            )}
            {report && (
              <div className="card shadow-sm mt-3">
                <div className="card-body">
                  <div className="d-flex justify-content-between align-items-start mb-2">
                    <span className="badge bg-primary">Scheda progetto</span>
                    <button className="btn btn-sm btn-outline-primary" onClick={downloadReport}>
                      Scarica (.md)
                    </button>
                  </div>
                  <AssistantMarkdown text={report.report_md} />
                </div>
              </div>
            )}
          </div>

          {/* Colonna evidenza */}
          <div className="col-lg-4">
            <div className="card shadow-sm mb-3">
              <div className="card-body">
                <h2 className="h6">Dataset trovati</h2>
                {datasets.length === 0 && (
                  <p className="text-muted mb-0">Compariranno durante l&apos;esplorazione.</p>
                )}
                <ul className="list-unstyled mb-0">
                  {datasets.map((d) => (
                    <li key={d.id} className="mb-2">
                      <a href={d.url} target="_blank" rel="noreferrer">{d.title}</a>
                      <br />
                      <small className="text-muted">
                        {"★".repeat(d.stars)}{"☆".repeat(Math.max(0, 5 - d.stars))} · {d.quality_note}
                      </small>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="card shadow-sm">
              <div className="card-body">
                <h2 className="h6">Progetti simili già finanziati</h2>
                {funding.length === 0 && (
                  <p className="text-muted mb-0">
                    Da OpenCoesione, per valutare la finanziabilità dell&apos;idea.
                  </p>
                )}
                <ul className="list-unstyled mb-0">
                  {funding.slice(0, 5).map((p) => (
                    <li key={p.clp} className="mb-2">
                      <span>{p.titolo}</span>
                      <br />
                      <small className="text-muted">
                        {euro(p.finanziamento_totale)} · ciclo {p.ciclo ?? "n/d"} · {p.stato ?? "n/d"}
                      </small>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </main>
    </DashboardGate>
  );
}
