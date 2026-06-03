"use client";

import { useState, useEffect, useRef } from "react";
import { Button, Input } from "design-react-kit";

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
      className="flex items-end gap-2 border-t border-[var(--color-border)] bg-white p-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="flex-1">
        <label htmlFor="chat-query" className="sr-only">
          Domanda
        </label>
        {/* BI Input typings don't include textarea-specific props (rows),
            so spread them as untyped extras. The underlying element is a
            <textarea> when type="textarea". */}
        <Input
          type="textarea"
          id="chat-query"
          innerRef={textareaRef as unknown as React.Ref<HTMLInputElement>}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          disabled={loading}
          placeholder="Scrivi una domanda… (Invio per inviare, Shift+Invio per andare a capo)"
          {...({ rows: 2 } as Record<string, unknown>)}
        />
      </div>
      <Button color="primary" type="submit" disabled={!canSubmit}>
        Invia
      </Button>
    </form>
  );
}
