"use client";

import { EXAMPLE_QUERIES } from "@/lib/examples";

type Props = {
  onPick: (query: string) => void;
  disabled: boolean;
};

export function ExampleQueries({ onPick, disabled }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {EXAMPLE_QUERIES.map((ex) => (
        <button
          key={ex.label}
          type="button"
          onClick={() => onPick(ex.query)}
          disabled={disabled}
          className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
        >
          {ex.label}
        </button>
      ))}
    </div>
  );
}
