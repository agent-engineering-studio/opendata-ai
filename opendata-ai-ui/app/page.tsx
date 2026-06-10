"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import type { ChatMessage, ChatRequest, Resource } from "@/lib/types";
import { apiFetch } from "@/lib/api";
import { ChatHeader } from "@/components/ChatHeader";
import { MessageList } from "@/components/MessageList";
import { ChatInput } from "@/components/ChatInput";
import { ExampleQueries } from "@/components/ExampleQueries";
import { SignInGate } from "@/components/SignInGate";

// Backend agent names → Italian labels for the rolling status string.
const SOURCE_LABEL: Record<string, string> = {
  ckan: "Catalogo CKAN",
  istat: "ISTAT",
  eurostat: "Eurostat",
  oecd: "OCSE",
  synth: "Sintesi",
};

type StreamEvent =
  | { event: "status"; source: string; phase: "start" | "end"; error?: string }
  | { event: "heartbeat"; in_flight: string[]; elapsed_ms: number }
  | { event: "result"; text: string; resources: Resource[] }
  | { event: "error"; message: string };

function statusLabel(ev: { source: string; phase: "start" | "end"; error?: string }): string {
  const label = SOURCE_LABEL[ev.source] ?? ev.source;
  if (ev.error) return `${label} ha riportato un errore — proseguo…`;
  if (ev.phase === "start") {
    return ev.source === "synth" ? "Sintesi finale in corso…" : `Interrogo ${label}…`;
  }
  return ev.source === "synth" ? "Sintesi completata" : `${label} ha risposto`;
}

function heartbeatLabel(ev: { in_flight: string[]; elapsed_ms: number }): string {
  const labels = ev.in_flight.map((s) => SOURCE_LABEL[s] ?? s);
  const human = labels.length > 1 ? labels.join(" + ") : labels[0] ?? "agente";
  const secs = Math.floor(ev.elapsed_ms / 1000);
  return `Ancora in lavorazione su ${human}… (${secs}s)`;
}

export default function Page() {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [prefill, setPrefill] = useState<string | undefined>(undefined);
  const [prefillKey, setPrefillKey] = useState<number>(0);

  function pickExample(query: string) {
    setPrefill(query);
    setPrefillKey((n) => n + 1);
  }

  async function send(query: string) {
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setLoading(true);
    setStatus(undefined);
    const t0 = performance.now();

    const body: ChatRequest = { query };

    try {
      const token = await getToken();
      const res = await apiFetch("/datasets/search/stream", {
        method: "POST",
        token,
        body: JSON.stringify(body),
      });

      if (!res.ok || !res.body) {
        setMessages((prev) => [
          ...prev,
          { role: "error", text: `Errore HTTP ${res.status}` },
        ]);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let final: { text: string; resources: Resource[] } | null = null;
      let streamError: string | null = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // NDJSON: each event is a complete JSON object on its own line.
        let nl: number;
        while ((nl = buffer.indexOf("\n")) !== -1) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          let ev: StreamEvent;
          try {
            ev = JSON.parse(line) as StreamEvent;
          } catch {
            continue;
          }
          if (ev.event === "status") {
            setStatus(statusLabel(ev));
          } else if (ev.event === "heartbeat") {
            setStatus(heartbeatLabel(ev));
          } else if (ev.event === "result") {
            final = { text: ev.text, resources: ev.resources ?? [] };
          } else if (ev.event === "error") {
            streamError = ev.message;
          }
        }
      }

      if (streamError) {
        setMessages((prev) => [...prev, { role: "error", text: streamError! }]);
      } else if (final) {
        const durationMs = performance.now() - t0;
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: final!.text,
            resources: final!.resources,
            durationMs,
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "error", text: "Lo stream è terminato senza una risposta." },
        ]);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setMessages((prev) => [
        ...prev,
        { role: "error", text: `Errore di rete: ${message}` },
      ]);
    } finally {
      setLoading(false);
      setStatus(undefined);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ChatHeader
        onReset={() => setMessages([])}
        canReset={messages.length > 0 && !loading}
      />
      <MessageList
        messages={messages}
        loading={loading}
        statusMessage={status}
        emptyState={
          <div className="space-y-3">
            <p className="text-slate-500">
              Fai una domanda: l&apos;orchestrator interroga in parallelo i
              portali CKAN e le fonti statistiche ufficiali (ISTAT
              {", Eurostat e OCSE se abilitate"}). Parti da uno degli esempi —
              il tag colorato indica la fonte attesa:
            </p>
            <ExampleQueries onPick={pickExample} disabled={loading} />
          </div>
        }
      />
      {messages.length > 0 ? (
        <div className="border-t border-slate-200 bg-slate-50 px-4 py-2">
          <ExampleQueries onPick={pickExample} disabled={loading} />
        </div>
      ) : null}
      <SignInGate
        signedIn={
          <ChatInput
            onSubmit={send}
            loading={loading}
            prefill={prefill}
            prefillKey={prefillKey}
          />
        }
      />
    </div>
  );
}
