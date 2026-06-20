"use client";

import { useState } from "react";

// The five skills published by the opendata-ai AgentCard, each with a ready
// example so the form is usable out of the box.
const SKILLS: { id: string; label: string; example: string; multiline: boolean }[] = [
  {
    id: "search_open_data",
    label: "search_open_data — cerca dataset",
    example: "popolazione di Milano per età, ultimi 5 anni",
    multiline: false,
  },
  {
    id: "find_geo_resources",
    label: "find_geo_resources — risorse geografiche",
    example: "confini delle regioni italiane",
    multiline: false,
  },
  {
    id: "classify_dataset",
    label: "classify_dataset — classifica (JSON)",
    example: JSON.stringify(
      {
        source: "ckan",
        dataset_id: "esempio-001",
        dataset_name: "Incidenti stradali per comune",
        taxonomy: ["sicurezza", "mobilità", "sanità"],
      },
      null,
      2,
    ),
    multiline: true,
  },
  {
    id: "assess_maturity",
    label: "assess_maturity — maturità ente",
    example: '{"entity":"Comune di Gioia del Colle","istat_code":"072021"}',
    multiline: false,
  },
  {
    id: "analyze_territory",
    label: "analyze_territory — SWOT + proposte (JSON)",
    example: JSON.stringify(
      { cod_comune: "072021", comune_nome: "Gioia del Colle", modalita: "idee" },
      null,
      2,
    ),
    multiline: true,
  },
];

type Card = { name?: string; version?: string; skills?: { id: string; name?: string }[] };

/** Best-effort: raccoglie tutti i campi `text` dentro gli artifacts del Task. */
function extractTexts(result: unknown): string[] {
  const out: string[] = [];
  const walk = (node: unknown) => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      node.forEach(walk);
      return;
    }
    const obj = node as Record<string, unknown>;
    if (typeof obj.text === "string" && obj.text.trim()) out.push(obj.text);
    if (typeof obj.data === "string" && obj.data.trim()) out.push(obj.data);
    Object.values(obj).forEach(walk);
  };
  // Limita la ricerca agli artifacts quando presenti, altrimenti tutto.
  const r = result as Record<string, unknown> | null;
  const root =
    r && typeof r === "object" && "result" in r ? (r.result as Record<string, unknown>) : r;
  const artifacts = root && typeof root === "object" ? (root as Record<string, unknown>).artifacts : null;
  walk(artifacts ?? result);
  return Array.from(new Set(out));
}

const box: React.CSSProperties = {
  background: "#fff",
  border: "1px solid #e6eaef",
  borderRadius: 12,
  padding: 16,
};
const label: React.CSSProperties = { fontWeight: 600, fontSize: 13, display: "block", marginBottom: 4 };
const input: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  border: "1px solid #d7dde5",
  borderRadius: 8,
  fontSize: 14,
  fontFamily: "inherit",
  boxSizing: "border-box",
};

export default function Page() {
  const [baseUrl, setBaseUrl] = useState("");
  const [token, setToken] = useState("");
  const [skillId, setSkillId] = useState(SKILLS[0].id);
  const [message, setMessage] = useState(SKILLS[0].example);
  const [busy, setBusy] = useState(false);
  const [card, setCard] = useState<Card | null>(null);
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  const skill = SKILLS.find((s) => s.id === skillId)!;

  function pickSkill(id: string) {
    setSkillId(id);
    const s = SKILLS.find((x) => x.id === id);
    if (s) setMessage(s.example);
  }

  async function loadCard() {
    setError(null);
    setCard(null);
    try {
      const qs = baseUrl.trim() ? `?baseUrl=${encodeURIComponent(baseUrl.trim())}` : "";
      const resp = await fetch(`/api/agent-card${qs}`);
      const data = await resp.json();
      if (!data.ok) throw new Error(data.error || "AgentCard non raggiungibile");
      setCard(data.card as Card);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function send() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const resp = await fetch("/api/a2a", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skill: skillId, message, token: token.trim(), baseUrl: baseUrl.trim() }),
      });
      const data = await resp.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const texts = result ? extractTexts((result as { result?: unknown }).result) : [];

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: "32px 20px 64px" }}>
      <h1 style={{ marginBottom: 4 }}>A2A Tester · opendata-ai</h1>
      <p style={{ color: "#5b6b7b", marginTop: 0, fontSize: 14 }}>
        Client minimale che chiama le skill A2A del backend via JSON-RPC{" "}
        <code>SendMessage</code>. La richiesta è proxata lato server (niente CORS).
      </p>

      <div style={{ ...box, marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <label style={label}>Backend URL (vuoto = default server)</label>
            <input
              style={input}
              placeholder="http://localhost:8000"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </div>
          <div>
            <label style={label}>Bearer token (opzionale)</label>
            <input
              style={input}
              type="password"
              placeholder="JWT Clerk o API key od_…"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={loadCard}
          style={{
            marginTop: 12,
            padding: "7px 14px",
            border: "1px solid #1b6fe3",
            background: "#fff",
            color: "#1b6fe3",
            borderRadius: 999,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Carica AgentCard
        </button>
        {card ? (
          <div style={{ marginTop: 12, fontSize: 13 }}>
            <strong>{card.name}</strong> v{card.version} — skill:{" "}
            {(card.skills ?? []).map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => pickSkill(s.id)}
                style={{
                  margin: "2px 4px 2px 0",
                  padding: "2px 8px",
                  border: "1px solid #d7dde5",
                  background: "#f6f8fa",
                  borderRadius: 999,
                  fontSize: 12,
                  cursor: "pointer",
                }}
                title="Usa questa skill"
              >
                {s.id}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div style={box}>
        <label style={label}>Skill</label>
        <select style={input} value={skillId} onChange={(e) => pickSkill(e.target.value)}>
          {SKILLS.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>

        <label style={{ ...label, marginTop: 12 }}>
          Messaggio {skill.multiline ? "(JSON)" : "(testo)"}
        </label>
        <textarea
          style={{ ...input, minHeight: skill.multiline ? 130 : 70, fontFamily: skill.multiline ? "ui-monospace, monospace" : "inherit" }}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />

        <button
          type="button"
          onClick={send}
          disabled={busy || !message.trim()}
          style={{
            marginTop: 12,
            padding: "9px 22px",
            border: 0,
            background: busy ? "#94a3b8" : "#1b6fe3",
            color: "#fff",
            borderRadius: 999,
            fontWeight: 600,
            cursor: busy ? "default" : "pointer",
          }}
        >
          {busy ? "Invio…" : "Invia"}
        </button>
      </div>

      {error ? (
        <div style={{ ...box, marginTop: 16, borderColor: "#f3b7c0", background: "#fdf2f4", color: "#a3162c" }}>
          {error}
        </div>
      ) : null}

      {texts.length > 0 ? (
        <div style={{ ...box, marginTop: 16 }}>
          <h2 style={{ fontSize: 16, marginTop: 0 }}>Risposta</h2>
          {texts.map((t, i) => (
            <pre
              key={i}
              style={{
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                background: "#f6f8fa",
                padding: 12,
                borderRadius: 8,
                fontSize: 13,
              }}
            >
              {t}
            </pre>
          ))}
        </div>
      ) : null}

      {result ? (
        <details style={{ ...box, marginTop: 16 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>JSON-RPC grezzo</summary>
          <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12, marginBottom: 0 }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </details>
      ) : null}
    </main>
  );
}
