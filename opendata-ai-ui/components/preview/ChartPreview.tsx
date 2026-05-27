"use client";

import { useCallback, useMemo, useState } from "react";
import Papa from "papaparse";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useProxyFetch } from "@/lib/useProxyFetch";

const MAX_CATEGORIES = 30; // cap bars after aggregation
const MAX_SERIES = 6;
const SERIES_COLORS = [
  "#2563eb", "#dc2626", "#059669", "#d97706",
  "#7c3aed", "#0891b2",
];

const TIME_RE = /^(time_period|time|date|anno|year|periodo|ref_period)$/i;
// Numeric columns whose header looks like an identifier are dimensions, not measures.
const IDENTIFIER_RE = /(^|[\s_(\-])(id|codice|cod|istat|cap|zip|pk|uuid|anno|year|nuts|geo)([\s_)\-]|$)/i;

type Row = Record<string, string>;

/** Italian/locale-aware numeric parse: "22,1" → 22.1, "1.234,5" → 1234.5. */
function toNumber(raw: string | undefined): number | null {
  if (raw == null) return null;
  let s = raw.trim();
  if (!s) return null;
  if (/,\d{1,3}$/.test(s) && s.includes(".")) s = s.replace(/\./g, "").replace(",", ".");
  else if (/,/.test(s) && !/\./.test(s)) s = s.replace(",", ".");
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function sample(rows: Row[], field: string): string[] {
  const out: string[] = [];
  for (const r of rows.slice(0, 80)) {
    const v = r[field];
    if (v != null && v !== "") out.push(v.trim());
  }
  return out;
}

function isNumericColumn(rows: Row[], field: string): boolean {
  const s = sample(rows, field);
  if (s.length === 0) return false;
  return s.filter((v) => toNumber(v) !== null).length / s.length > 0.8;
}

/** A numeric column is a *measure* (a quantity to chart) unless it's an identifier
 *  (year, ISTAT code, leading-zero code, id). Those are dimensions. */
function isMeasureColumn(rows: Row[], field: string): boolean {
  if (!isNumericColumn(rows, field)) return false;
  if (IDENTIFIER_RE.test(field)) return false;
  const s = sample(rows, field);
  // leading-zero codes (e.g. "045") → identifier
  if (s.some((v) => /^0\d+$/.test(v))) return false;
  // year-like (1900–2100), mostly → identifier
  const yearish = s.filter((v) => /^(19|20)\d{2}$/.test(v)).length;
  if (yearish / s.length > 0.8) return false;
  return true;
}

function distinct(rows: Row[], field: string): number {
  return new Set(rows.map((r) => r[field]).filter((v) => v != null && v !== "")).size;
}

type Classified = {
  fields: string[];
  rows: Row[];
  measures: string[];
  dimensions: string[];
};

function classify(content: string): Classified {
  const parsed = Papa.parse<Row>(content, {
    header: true,
    skipEmptyLines: true,
    dynamicTyping: false,
  });
  const fields = (parsed.meta.fields ?? []).filter(
    (f): f is string => typeof f === "string" && f.length > 0,
  );
  const rows = (parsed.data ?? []).filter(
    (r): r is Row => r != null && typeof r === "object",
  );
  const measures = fields.filter((f) => isMeasureColumn(rows, f));
  const dimensions = fields.filter((f) => !measures.includes(f));
  return { fields, rows, measures, dimensions };
}

/** Default dimension to group by: a categorical column with a sensible number of
 *  distinct values (2..MAX_CATEGORIES), preferring non-identifier text columns. */
function pickDefaultDimension(rows: Row[], dimensions: string[]): string | null {
  const scored = dimensions
    .map((f) => ({ f, d: distinct(rows, f), id: IDENTIFIER_RE.test(f) }))
    .filter((x) => x.d >= 2 && x.d <= MAX_CATEGORIES);
  if (scored.length === 0) return dimensions[0] ?? null;
  // prefer non-identifier dimensions; among them the most granular (max distinct)
  const textDims = scored.filter((x) => !x.id);
  const pool = textDims.length ? textDims : scored;
  pool.sort((a, b) => b.d - a.d);
  return pool[0].f;
}

type Aggregated = {
  data: Record<string, number | string>[];
  truncated: boolean;
};

/** Group rows by `dim` and SUM each selected measure. Sort categories by the
 *  total of the first measure (desc) and cap at MAX_CATEGORIES. */
function aggregate(rows: Row[], dim: string, measures: string[]): Aggregated {
  const byCat = new Map<string, Record<string, number>>();
  for (const r of rows) {
    const cat = (r[dim] ?? "").trim() || "(vuoto)";
    let acc = byCat.get(cat);
    if (!acc) {
      acc = {};
      for (const m of measures) acc[m] = 0;
      byCat.set(cat, acc);
    }
    for (const m of measures) {
      const n = toNumber(r[m]);
      if (n !== null) acc[m] += n;
    }
  }
  let entries = Array.from(byCat.entries());
  const first = measures[0];
  if (first) entries.sort((a, b) => (b[1][first] ?? 0) - (a[1][first] ?? 0));
  const truncated = entries.length > MAX_CATEGORIES;
  entries = entries.slice(0, MAX_CATEGORIES);
  const data = entries.map(([cat, sums]) => ({ [dim]: cat, ...sums }));
  return { data, truncated };
}

function ChartFromContent({ content }: { content: string }) {
  const { rows, measures, dimensions } = useMemo(() => classify(content), [content]);
  const defaultDim = useMemo(
    () => pickDefaultDimension(rows, dimensions),
    [rows, dimensions],
  );
  const [dim, setDim] = useState<string | null>(defaultDim);
  const [activeMeasures, setActiveMeasures] = useState<string[]>(
    measures.slice(0, MAX_SERIES),
  );

  const effectiveDim = dim ?? defaultDim;
  const series = activeMeasures.length ? activeMeasures : measures.slice(0, 1);

  const agg = useMemo(() => {
    if (!effectiveDim || series.length === 0) return null;
    return aggregate(rows, effectiveDim, series);
  }, [rows, effectiveDim, series]);

  if (measures.length === 0 || !effectiveDim || !agg) {
    return (
      <div className="text-xs text-slate-500">
        Questo CSV non contiene misure numeriche aggregabili. Usa la vista tabella.
      </div>
    );
  }

  // Time-ordered dimension → line; otherwise bar (aggregated categories).
  const isTime = TIME_RE.test(effectiveDim);
  const Chart = isTime ? LineChart : BarChart;
  // Sort time categories chronologically.
  const data = isTime
    ? [...agg.data].sort((a, b) => String(a[effectiveDim]).localeCompare(String(b[effectiveDim])))
    : agg.data;

  function toggleMeasure(m: string) {
    setActiveMeasures((prev) =>
      prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m].slice(0, MAX_SERIES),
    );
  }

  return (
    <div className="space-y-2">
      {/* Controls: group-by dimension + measures */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <label className="flex items-center gap-1">
          <span className="text-slate-500">Raggruppa per</span>
          <select
            value={effectiveDim}
            onChange={(e) => setDim(e.target.value)}
            className="rounded border border-slate-300 bg-white px-1.5 py-0.5"
          >
            {dimensions.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <span className="text-slate-500">Misure:</span>
        {measures.map((m) => (
          <label key={m} className="flex items-center gap-1 text-slate-700">
            <input
              type="checkbox"
              checked={series.includes(m)}
              onChange={() => toggleMeasure(m)}
            />
            {m}
          </label>
        ))}
      </div>

      {agg.truncated ? (
        <div className="rounded border border-yellow-300 bg-yellow-50 px-3 py-1 text-xs text-yellow-800">
          Mostrate le prime {MAX_CATEGORIES} categorie (per somma decrescente).
        </div>
      ) : null}

      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <Chart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey={effectiveDim}
              tick={{ fontSize: 10 }}
              angle={isTime ? 0 : -25}
              textAnchor={isTime ? "middle" : "end"}
              height={isTime ? 24 : 64}
              interval={0}
            />
            <YAxis tick={{ fontSize: 11 }} width={52} />
            <Tooltip contentStyle={{ fontSize: 12 }} />
            {series.length > 1 ? <Legend wrapperStyle={{ fontSize: 11 }} /> : null}
            {series.map((s, i) =>
              isTime ? (
                <Line
                  key={s}
                  type="monotone"
                  dataKey={s}
                  stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                  dot={false}
                  strokeWidth={2}
                />
              ) : (
                <Bar key={s} dataKey={s} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
              ),
            )}
          </Chart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-slate-400">
        Valori = somma di {series.join(", ")} per {effectiveDim}.
      </p>
    </div>
  );
}

function LazyChart({ url }: { url: string }) {
  const decode = useCallback((resp: Response) => resp.text(), []);
  const state = useProxyFetch<string>(url, decode);
  if (state.status === "loading")
    return <div className="text-xs text-slate-500">Caricamento dati per il grafico…</div>;
  if (state.status === "error")
    return (
      <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
        Impossibile scaricare i dati: {state.message}
      </div>
    );
  if (state.magic)
    return (
      <div className="text-xs text-slate-500">
        Il file non è testo tabellare ({state.magic}); grafico non disponibile.
      </div>
    );
  return <ChartFromContent content={state.data} />;
}

/** Heuristic used by the parent to decide whether to offer the chart toggle:
 *  at least one numeric measure and at least one dimension to group by. */
export function isChartable(content: string | null | undefined): boolean {
  if (!content) return false;
  const { measures, dimensions, rows } = classify(content.slice(0, 8192));
  return measures.length > 0 && dimensions.length > 0 && rows.length >= 2;
}

export function ChartPreview({
  content,
  url,
}: {
  content?: string | null;
  url?: string;
}) {
  if (content) return <ChartFromContent content={content} />;
  if (url) return <LazyChart url={url} />;
  return null;
}
