"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useProxyFetch } from "@/lib/useProxyFetch";

type Sheet = {
  name: string;
  rows: string[][];
};

type Workbook = {
  sheets: Sheet[];
};

async function decodeXlsx(resp: Response): Promise<Workbook> {
  const buf = await resp.arrayBuffer();
  // Code-split: SheetJS is loaded only when the user expands an XLSX preview.
  const XLSX = await import("xlsx");
  const wb = XLSX.read(buf, { type: "array" });
  const sheets: Sheet[] = wb.SheetNames.map((name) => {
    const ws = wb.Sheets[name];
    const rows = XLSX.utils.sheet_to_json<string[]>(ws, {
      header: 1,
      blankrows: false,
      defval: "",
      raw: false,
    });
    return { name, rows };
  });
  return { sheets };
}

const ROW_HEIGHT = 32;

function SheetTable({ sheet }: { sheet: Sheet }) {
  const header = sheet.rows[0] ?? [];
  const body = sheet.rows.slice(1);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({
    count: body.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  if (sheet.rows.length === 0) {
    return <div className="text-xs text-slate-500">Foglio vuoto.</div>;
  }

  return (
    <div className="space-y-2">
      <div className="text-xs text-slate-500">
        {body.length} righ{body.length === 1 ? "a" : "e"} · {header.length}{" "}
        colonn{header.length === 1 ? "a" : "e"}
      </div>
      <div
        ref={scrollRef}
        className="max-h-96 overflow-auto rounded border border-slate-200"
      >
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 bg-slate-100">
            <tr>
              {header.map((h, i) => (
                <th
                  key={i}
                  className="border-b border-slate-200 px-2 py-1 text-left font-semibold text-slate-700"
                >
                  {String(h ?? "")}
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
              const row = body[vi.index] ?? [];
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
                  {header.map((_, i) => {
                    const value = String(row[i] ?? "");
                    return (
                      <td
                        key={i}
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

export function XlsxPreview({ url }: { url: string }) {
  const decode = useCallback(decodeXlsx, []);
  const state = useProxyFetch<Workbook>(url, decode);
  const [activeIdx, setActiveIdx] = useState(0);

  const active = useMemo(() => {
    if (state.status !== "ok") return null;
    return state.data.sheets[activeIdx] ?? state.data.sheets[0] ?? null;
  }, [state, activeIdx]);

  if (state.status === "loading") {
    return <div className="text-xs text-slate-500">Caricamento XLSX…</div>;
  }
  if (state.status === "error") {
    return (
      <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
        Impossibile aprire il file XLSX: {state.message}
      </div>
    );
  }
  if (!active) {
    return (
      <div className="text-xs text-slate-500">
        Nessun foglio trovato nel file.
      </div>
    );
  }

  const sheets = state.data.sheets;
  return (
    <div className="space-y-2">
      {sheets.length > 1 ? (
        <div className="flex flex-wrap gap-1">
          {sheets.map((s, i) => (
            <button
              key={s.name + i}
              type="button"
              onClick={() => setActiveIdx(i)}
              className={`rounded border px-2 py-0.5 text-xs ${
                i === activeIdx
                  ? "border-blue-500 bg-blue-50 text-blue-800"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>
      ) : null}
      <SheetTable sheet={active} />
    </div>
  );
}
