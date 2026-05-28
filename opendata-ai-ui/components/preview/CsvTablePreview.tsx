"use client";

import { useCallback, useMemo } from "react";
import Papa from "papaparse";
import { useProxyFetch } from "@/lib/useProxyFetch";

type Row = Record<string, string>;

type ParsedCsv = {
  fields: string[];
  rows: Row[];
  errors: number;
};

// Cap rendered rows: the captured/downloaded content is already byte-capped, but
// dumping thousands of <tr> into the DOM lags. The chart view / download cover the
// full series; the table is a readable sample.
const MAX_ROWS = 500;

function parseCsv(content: string): ParsedCsv {
  const result = Papa.parse<Row>(content, {
    header: true,
    delimiter: "", // auto-detect (handles SDMX comma + Italian semicolon CSVs)
    skipEmptyLines: true,
    dynamicTyping: false,
  });
  const fields = (result.meta.fields ?? []).filter(
    (f): f is string => typeof f === "string" && f.length > 0,
  );
  const rows = (result.data ?? []).filter(
    (r): r is Row => r != null && typeof r === "object",
  );
  return { fields, rows, errors: result.errors.length };
}

const _NUM_RE = /^-?\s*\d{1,3}([.,]\d{3})*([.,]\d+)?\s*%?$/;

/** A column is numeric if most of its sampled non-empty cells parse as numbers. */
function numericColumns(fields: string[], rows: Row[]): Set<string> {
  const out = new Set<string>();
  for (const f of fields) {
    let seen = 0;
    let num = 0;
    for (const r of rows.slice(0, 50)) {
      const v = (r[f] ?? "").trim();
      if (!v) continue;
      seen++;
      if (_NUM_RE.test(v)) num++;
    }
    if (seen > 0 && num / seen > 0.8) out.add(f);
  }
  return out;
}

function CsvTable({ content }: { content: string }) {
  const { fields, rows, errors } = useMemo(() => parseCsv(content), [content]);
  const numeric = useMemo(() => numericColumns(fields, rows), [fields, rows]);

  // Parser couldn't find a header row → show the raw text rather than an empty grid.
  if (fields.length === 0) {
    return (
      <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-3 font-mono text-xs whitespace-pre-wrap text-slate-800">
        {content.slice(0, 20000)}
      </pre>
    );
  }

  const shown = rows.slice(0, MAX_ROWS);

  return (
    <div className="space-y-2">
      {errors > 0 ? (
        <div className="rounded border border-yellow-300 bg-yellow-50 px-3 py-1 text-xs text-yellow-800">
          Formato CSV non standard — alcune righe potrebbero essere imprecise
          ({errors} segnalazion{errors === 1 ? "e" : "i"})
        </div>
      ) : null}
      <div className="text-xs text-slate-500">
        {rows.length.toLocaleString("it-IT")} righ{rows.length === 1 ? "a" : "e"} ·{" "}
        {fields.length} colonn{fields.length === 1 ? "a" : "e"}
        {rows.length > MAX_ROWS ? ` · mostrate le prime ${MAX_ROWS}` : ""}
      </div>
      <div className="max-h-96 overflow-auto rounded border border-slate-200">
        <table className="min-w-full border-collapse text-xs">
          <thead>
            <tr className="sticky top-0 z-10">
              {fields.map((f) => (
                <th
                  key={f}
                  className={`whitespace-nowrap border-b border-slate-200 bg-slate-100 px-2.5 py-1.5 font-semibold text-slate-700 ${
                    numeric.has(f) ? "text-right" : "text-left"
                  }`}
                >
                  {f}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, i) => (
              <tr key={i} className={i % 2 === 1 ? "bg-slate-50/60" : "bg-white"}>
                {fields.map((f) => {
                  const value = row[f] ?? "";
                  return (
                    <td
                      key={f}
                      title={value}
                      className={`max-w-[22rem] truncate border-b border-slate-100 px-2.5 py-1 text-slate-800 ${
                        numeric.has(f)
                          ? "text-right font-mono tabular-nums"
                          : "text-left"
                      }`}
                    >
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LazyCsvTable({ url }: { url: string }) {
  const decode = useCallback((resp: Response) => resp.text(), []);
  const state = useProxyFetch<string>(url, decode);

  if (state.status === "loading") {
    return <div className="text-xs text-slate-500">Caricamento CSV…</div>;
  }
  if (state.status === "error") {
    return (
      <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
        Impossibile scaricare il CSV: {state.message}
      </div>
    );
  }
  if (state.magic) {
    return (
      <div className="rounded border border-yellow-300 bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
        Il file dichiarato come CSV è in realtà un archivio {state.magic}.
        Apri il link per scaricarlo.
      </div>
    );
  }
  return <CsvTable content={state.data} />;
}

export function CsvTablePreview({
  content,
  url,
}: {
  content?: string | null;
  url?: string;
}) {
  if (content) return <CsvTable content={content} />;
  if (url) return <LazyCsvTable url={url} />;
  return null;
}
