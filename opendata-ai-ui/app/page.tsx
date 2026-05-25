"use client";

import { useState } from "react";
import type { ChatMessage, ChatRequest, ChatResponse } from "@/lib/types";
import { ChatHeader } from "@/components/ChatHeader";
import { MessageList } from "@/components/MessageList";
import { ChatInput } from "@/components/ChatInput";
import { ExampleQueries } from "@/components/ExampleQueries";

export default function Page() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [prefill, setPrefill] = useState<string | undefined>(undefined);
  const [prefillKey, setPrefillKey] = useState<number>(0);

  function pickExample(query: string) {
    setPrefill(query);
    setPrefillKey((n) => n + 1);
  }

  async function send(query: string) {
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setLoading(true);
    const t0 = performance.now();

    const body: ChatRequest = { query };

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const text = await res.text();
      let parsed: ChatResponse | { error: string };
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = { error: "Risposta non valida dal proxy" };
      }

      const durationMs = performance.now() - t0;

      if (!res.ok || "error" in parsed) {
        const errText =
          "error" in parsed ? parsed.error : `Errore HTTP ${res.status}`;
        setMessages((prev) => [...prev, { role: "error", text: errText }]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: parsed.text,
            resources: parsed.resources ?? [],
            durationMs,
          },
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
    }
  }

  return (
    <div className="flex h-screen flex-col">
      <ChatHeader
        onReset={() => setMessages([])}
        canReset={messages.length > 0 && !loading}
      />
      <MessageList
        messages={messages}
        loading={loading}
        emptyState={
          <div className="space-y-3">
            <p className="text-slate-500">
              Fai una domanda: l&apos;agent cercherà nei portali CKAN
              disponibili. Puoi partire da uno degli esempi:
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
      <ChatInput
        onSubmit={send}
        loading={loading}
        prefill={prefill}
        prefillKey={prefillKey}
      />
    </div>
  );
}
