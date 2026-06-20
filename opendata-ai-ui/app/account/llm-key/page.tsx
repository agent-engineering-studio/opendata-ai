"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { DashboardGate } from "@/components/DashboardGate";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

type Provider = "claude" | "ollama_cloud" | "ollama_local";

type Status = {
  configured: boolean;
  provider?: string | null;
  model?: string | null;
};

const PROVIDERS: { id: Provider; label: string; hint: string; secretLabel: string; needsModel: boolean }[] = [
  {
    id: "claude",
    label: "Claude API (Anthropic)",
    hint: "La tua chiave Anthropic (inizia con sk-ant-…). Da console.anthropic.com.",
    secretLabel: "Chiave API Claude",
    needsModel: false,
  },
  {
    id: "ollama_cloud",
    label: "Ollama Cloud",
    hint: "La tua chiave Ollama Cloud. Il modello lo scegli tu (lasciato vuoto: default di sistema).",
    secretLabel: "Chiave API Ollama Cloud",
    needsModel: true,
  },
  {
    id: "ollama_local",
    label: "Ollama locale / on-prem",
    hint: "URL di un server Ollama raggiungibile dal backend (es. http://localhost:11434).",
    secretLabel: "URL del server Ollama",
    needsModel: true,
  },
];

function Inner() {
  const { getToken } = useAuth();
  const [status, setStatus] = useState<Status | null>(null);
  const [provider, setProvider] = useState<Provider>("claude");
  const [secret, setSecret] = useState("");
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const meta = PROVIDERS.find((p) => p.id === provider)!;

  const load = useCallback(async () => {
    try {
      const token = await getToken();
      const resp = await apiFetch("/account/llm-key", { token });
      if (resp.ok) setStatus(await resp.json());
    } catch {
      /* status stays null — form still usable */
    }
  }, [getToken]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const token = await getToken();
      const resp = await apiFetch("/account/llm-key", {
        token,
        method: "PUT",
        body: JSON.stringify({
          provider,
          api_key: secret.trim(),
          model: meta.needsModel && model.trim() ? model.trim() : null,
        }),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail.detail || `Errore ${resp.status}`);
      }
      setSecret("");
      setMsg({ kind: "ok", text: "Chiave salvata. Ora puoi usare le analisi." });
      await load();
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setMsg(null);
    try {
      const token = await getToken();
      const resp = await apiFetch("/account/llm-key", { token, method: "DELETE" });
      if (!resp.ok && resp.status !== 204) throw new Error(`Errore ${resp.status}`);
      setMsg({ kind: "ok", text: "Chiave rimossa." });
      await load();
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof Error ? err.message : "Errore" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container py-5" style={{ maxWidth: 760 }}>
      <p className="text-muted small mb-2">
        <Link href="/esplora">← Torna a Esplora</Link>
      </p>
      <h1 className="mb-3">La tua chiave LLM</h1>
      <p className="lead text-muted">
        Per usare le analisi puoi configurare una <strong>tua chiave</strong> (Claude API,
        Ollama Cloud o un Ollama locale) — in alternativa all&apos;abbonamento. La chiave è
        cifrata e non viene mai mostrata di nuovo.
      </p>

      {status?.configured && (
        <div className="alert alert-success d-flex justify-content-between align-items-center" role="status">
          <span>
            Configurata: <strong>{status.provider}</strong>
            {status.model ? ` · modello ${status.model}` : ""}
          </span>
          <button type="button" className="btn btn-outline-danger btn-sm" disabled={busy} onClick={remove}>
            Rimuovi
          </button>
        </div>
      )}

      <form onSubmit={save} className="card shadow-sm mt-3">
        <div className="card-body">
          <div className="mb-3">
            <label className="form-label fw-semibold" htmlFor="provider">Provider</label>
            <select
              id="provider"
              className="form-select"
              value={provider}
              onChange={(e) => setProvider(e.target.value as Provider)}
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <div className="form-text">{meta.hint}</div>
          </div>

          <div className="mb-3">
            <label className="form-label fw-semibold" htmlFor="secret">{meta.secretLabel}</label>
            <input
              id="secret"
              className="form-control font-monospace"
              type={provider === "ollama_local" ? "text" : "password"}
              autoComplete="off"
              placeholder={provider === "ollama_local" ? "http://localhost:11434" : "•••••••••••"}
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              required
            />
          </div>

          {meta.needsModel && (
            <div className="mb-3">
              <label className="form-label fw-semibold" htmlFor="model">
                Modello <span className="text-muted fw-normal">(opzionale)</span>
              </label>
              <input
                id="model"
                className="form-control font-monospace"
                placeholder={provider === "ollama_cloud" ? "es. gpt-oss:120b" : "es. qwen2.5:16k"}
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
            </div>
          )}

          {msg && (
            <div className={`alert ${msg.kind === "ok" ? "alert-success" : "alert-danger"} py-2`} role="alert">
              {msg.text}
            </div>
          )}

          <button type="submit" className="btn btn-primary" disabled={busy || !secret.trim()}>
            {busy ? "Salvataggio…" : "Salva chiave"}
          </button>
        </div>
      </form>

      <p className="small text-muted mt-3">
        Preferisci non gestire una chiave? Puoi{" "}
        <Link href="/sostieni">sostenere il progetto con un abbonamento</Link> e usare i
        modelli messi a disposizione.
      </p>
    </div>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <Inner />
    </DashboardGate>
  );
}
