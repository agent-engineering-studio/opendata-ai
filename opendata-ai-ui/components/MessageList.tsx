"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/types";
import { Message } from "./Message";

type Props = {
  messages: ChatMessage[];
  loading: boolean;
  statusMessage?: string;
  emptyState?: React.ReactNode;
};

export function MessageList({ messages, loading, statusMessage, emptyState }: Props) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, loading, statusMessage]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="max-w-md text-center">
          {emptyState ?? (
            <p className="text-slate-500">
              Fai una domanda al portale CKAN selezionato. Puoi partire da uno
              degli esempi qui sotto.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
      {messages.map((m, i) => (
        <Message key={i} message={m} />
      ))}
      {loading ? (
        <div className="flex justify-start">
          <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-2 text-sm text-slate-500 shadow-sm">
            <span className="inline-block animate-pulse">
              {statusMessage ?? "L’agent sta pensando…"}
            </span>
          </div>
        </div>
      ) : null}
      <div ref={bottomRef} />
    </div>
  );
}
