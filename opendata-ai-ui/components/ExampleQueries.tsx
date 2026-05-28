"use client";

import { EXAMPLE_QUERIES, type ExampleQuery } from "@/lib/examples";

type Props = {
  onPick: (query: string) => void;
  disabled: boolean;
};

function sourceBadgeColor(source: ExampleQuery["source"]): string {
  if (source === "ckan") return "bg-violet-100 text-violet-800";
  if (source === "istat") return "bg-amber-100 text-amber-800";
  if (source === "eurostat") return "bg-sky-100 text-sky-800";
  if (source === "oecd") return "bg-rose-100 text-rose-800";
  if (source === "cross") return "bg-slate-200 text-slate-800";
  return "";
}

function sourceLabel(source: ExampleQuery["source"]): string {
  if (source === "cross") return "multi";
  return source ?? "";
}

export function ExampleQueries({ onPick, disabled }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {EXAMPLE_QUERIES.map((ex) => (
        <button
          key={ex.label}
          type="button"
          onClick={() => onPick(ex.query)}
          disabled={disabled}
          className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
        >
          {ex.source ? (
            <span
              className={`inline-flex justify-center rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${sourceBadgeColor(ex.source)}`}
            >
              {sourceLabel(ex.source)}
            </span>
          ) : null}
          <span>{ex.label}</span>
        </button>
      ))}
    </div>
  );
}
