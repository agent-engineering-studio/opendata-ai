"use client";

import { useState, useEffect, useRef } from "react";

type Props = {
  onSubmit: (query: string) => void;
  loading: boolean;
  prefill?: string;
  prefillKey?: number;
};

export function ChatInput({ onSubmit, loading, prefill, prefillKey }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (prefill !== undefined) {
      setValue(prefill);
      textareaRef.current?.focus();
    }
  }, [prefill, prefillKey]);

  const trimmed = value.trim();
  const canSubmit = !loading && trimmed.length > 0;

  function submit() {
    if (!canSubmit) return;
    onSubmit(trimmed);
    setValue("");
  }

  return (
    <form
      className="flex items-end gap-2 border-t border-slate-200 bg-white p-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={2}
        disabled={loading}
        placeholder="Scrivi una domanda… (Invio per inviare, Shift+Invio per andare a capo)"
        className="flex-1 resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50"
      />
      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:bg-slate-300"
      >
        Invia
      </button>
    </form>
  );
}
