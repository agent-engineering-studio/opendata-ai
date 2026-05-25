"use client";

import { useMemo, useRef } from "react";
import Papa from "papaparse";
import { useVirtualizer } from "@tanstack/react-virtual";

type ParsedCsv = {
  fields: string[];
  rows: Record<string, string>[];
  errors: number;
};

function parseCsv(content: string): ParsedCsv {
  const result = Papa.parse<Record<string, string>>(content, {
    header: true,
    delimiter: "",
    skipEmptyLines: true,
    dynamicTyping: false,
  });
  const fields = (result.meta.fields ?? []).filter(
    (f): f is string => typeof f === "string" && f.length > 0,
  );
  const rows = (result.data ?? []).filter(
    (r): r is Record<string, string> => r != null && typeof r === "object",
  );
  return { fields, rows, errors: result.errors.length };
}

const ROW_HEIGHT = 32;

export function CsvTablePreview({ content }: { content: string }) {
  const { fields, rows, errors } = useMemo(() => parseCsv(content), [content]);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  if (fields.length === 0) {
    return (
      <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-3 font-mono text-xs whitespace-pre-wrap text-slate-800">
        {content}
      </pre>
    );
  }

  return (
    <div className="space-y-2">
      {errors > 0 ? (
        <div className="rounded border border-yellow-300 bg-yellow-50 px-3 py-1 text-xs text-yellow-800">
          Formato CSV non standard — alcune righe potrebbero essere errate
          ({errors} segnalazion{errors === 1 ? "e" : "i"})
        </div>
      ) : null}
      <div className="text-xs text-slate-500">
        {rows.length} righ{rows.length === 1 ? "a" : "e"} · {fields.length}{" "}
        colonn{fields.length === 1 ? "a" : "e"}
      </div>
      <div
        ref={scrollRef}
        className="max-h-96 overflow-auto rounded border border-slate-200"
      >
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 bg-slate-100">
            <tr>
              {fields.map((f) => (
                <th
                  key={f}
                  className="border-b border-slate-200 px-2 py-1 text-left font-semibold text-slate-700"
                >
                  {f}
                </th>
              ))}
            </tr>
          </thead>
          <tbody
            style={{
              position: "relative",
              height: virtualizer.getTotalSize(),
              display: "block",
            }}
          >
            {virtualizer.getVirtualItems().map((vi) => {
              const row = rows[vi.index];
              return (
                <tr
                  key={vi.key}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: vi.size,
                    transform: `translateY(${vi.start}px)`,
                    display: "table",
                    tableLayout: "fixed",
                  }}
                >
                  {fields.map((f) => {
                    const value = row?.[f] ?? "";
                    return (
                      <td
                        key={f}
                        title={value}
                        className="overflow-hidden text-ellipsis whitespace-nowrap border-b border-slate-100 px-2 py-1"
                      >
                        {value}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
