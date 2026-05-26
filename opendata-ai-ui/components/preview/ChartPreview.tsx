"use client";

import { useCallback, useMemo } from "react";
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

const MAX_POINTS = 300;
const MAX_SERIES = 6;
const SERIES_COLORS = [
  "#2563eb", "#dc2626", "#059669", "#d97706",
  "#7c3aed", "#0891b2",
];

const TIME_RE = /^(time_period|time|date|anno|year|periodo|ref_period)$/i;

type Row = Record<string, string>;

/** Italian/locale-aware numeric parse: "22,1" → 22.1, "1.234,5" → 1234.5. */
function toNumber(raw: string | undefined): number | null {
  if (raw == null) return null;
  let s = raw.trim();
  if (!s) return null;
  // 1.234,56 (it) → 1234.56 ; 1,234.56 (en) → 1234.56
  if (/,\d{1,3}$/.test(s) && s.includes(".")) s = s.replace(/\./g, "").replace(",", ".");
  else if (/,/.test(s) && !/\./.test(s)) s = s.replace(",", ".");
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function isNumericColumn(rows: Row[], field: string): boolean {
  let seen = 0;
  let numeric = 0;
  for (const r of rows.slice(0, 50)) {
    const v = r[field];
    if (v == null || v === "") continue;
    seen++;
    if (toNumber(v) !== null) numeric++;
  }
  return seen > 0 && numeric / seen > 0.8;
}

type ChartSpec =
  | {
      kind: "line" | "bar";
      xField: string;
      series: { key: string; label: string }[];
      data: Record<string, number | string>[];
      truncated: boolean;
      tooManySeries: boolean;
    }
  | { kind: "none" };

function buildChartSpec(fields: string[], rows: Row[]): ChartSpec {
  if (fields.length === 0 || rows.length < 2) return { kind: "none" };

  const timeField = fields.find((f) => TIME_RE.test(f));
  const hasObsValue = fields.includes("OBS_VALUE");

  // ── SDMX-CSV: x=TIME_PERIOD, y=OBS_VALUE, one grouping dimension → series ──
  if (hasObsValue && timeField) {
    const exclude = new Set([timeField, "OBS_VALUE"]);
    // Candidate grouping dims: code-like columns (not labels/notes) with >1 value.
    const dimCandidates = fields.filter((f) => {
      if (exclude.has(f)) return false;
      if (/label|note|flag|obs_status|unit_meas/i.test(f)) return false;
      const distinct = new Set(rows.map((r) => r[f]).filter(Boolean));
      return distinct.size > 1 && distinct.size <= MAX_SERIES * 2;
    });
    // Pick the dimension with the fewest (≥2) distinct values as the series splitter.
    let groupField: string | null = null;
    let best = Infinity;
    for (const f of dimCandidates) {
      const distinct = new Set(rows.map((r) => r[f]).filter(Boolean)).size;
      if (distinct >= 2 && distinct < best) {
        best = distinct;
        groupField = f;
      }
    }

    const xs = Array.from(new Set(rows.map((r) => r[timeField]).filter(Boolean))).sort();
    const byX = new Map<string, Record<string, number | string>>();
    for (const x of xs) byX.set(x, { [timeField]: x });

    const seriesKeys = new Set<string>();
    for (const r of rows) {
      const x = r[timeField];
      const y = toNumber(r["OBS_VALUE"]);
      if (!x || y === null) continue;
      const key = groupField ? r[groupField] || "—" : "OBS_VALUE";
      seriesKeys.add(key);
      const point = byX.get(x);
      if (point) point[key] = y;
    }

    let series = Array.from(seriesKeys).map((k) => ({ key: k, label: k }));
    const tooManySeries = series.length > MAX_SERIES;
    if (tooManySeries) series = series.slice(0, MAX_SERIES);

    return {
      kind: "line",
      xField: timeField,
      series,
      data: Array.from(byX.values()),
      truncated: false,
      tooManySeries,
    };
  }

  // ── Generic CSV: x = first non-numeric column, y = numeric columns ──
  const numericFields = fields.filter((f) => isNumericColumn(rows, f));
  if (numericFields.length === 0) return { kind: "none" };
  const xField = fields.find((f) => !numericFields.includes(f)) ?? fields[0];
  const ys = numericFields.filter((f) => f !== xField).slice(0, MAX_SERIES);
  if (ys.length === 0) return { kind: "none" };

  const sliced = rows.slice(0, MAX_POINTS);
  const data = sliced.map((r) => {
    const point: Record<string, number | string> = { [xField]: r[xField] ?? "" };
    for (const y of ys) {
      const n = toNumber(r[y]);
      if (n !== null) point[y] = n;
    }
    return point;
  });

  // Time-ish x → line, otherwise bar.
  const xLooksOrdered = TIME_RE.test(xField) || /year|anno|date|period/i.test(xField);
  return {
    kind: xLooksOrdered ? "line" : "bar",
    xField,
    series: ys.map((y) => ({ key: y, label: y })),
    data,
    truncated: rows.length > MAX_POINTS,
    tooManySeries: numericFields.length - 1 > MAX_SERIES,
  };
}

function ChartFromContent({ content }: { content: string }) {
  const spec = useMemo(() => {
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
    return buildChartSpec(fields, rows);
  }, [content]);

  if (spec.kind === "none") {
    return (
      <div className="text-xs text-slate-500">
        Questo CSV non sembra contenere una serie numerica rappresentabile come
        grafico. Usa la vista tabella.
      </div>
    );
  }

  const Chart = spec.kind === "line" ? LineChart : BarChart;

  return (
    <div className="space-y-2">
      {(spec.truncated || spec.tooManySeries) && (
        <div className="rounded border border-yellow-300 bg-yellow-50 px-3 py-1 text-xs text-yellow-800">
          {spec.truncated && `Mostrati i primi ${MAX_POINTS} punti. `}
          {spec.tooManySeries && `Mostrate le prime ${MAX_SERIES} serie.`}
        </div>
      )}
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <Chart data={spec.data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={spec.xField} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip contentStyle={{ fontSize: 12 }} />
            {spec.series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
            {spec.series.map((s, i) =>
              spec.kind === "line" ? (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.label}
                  stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                  dot={false}
                  strokeWidth={2}
                  connectNulls
                />
              ) : (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  fill={SERIES_COLORS[i % SERIES_COLORS.length]}
                />
              ),
            )}
          </Chart>
        </ResponsiveContainer>
      </div>
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

/** Heuristic used by the parent to decide whether to offer the chart toggle. */
export function isChartable(content: string | null | undefined): boolean {
  if (!content) return false; // lazy-fetch path still offers it via URL separately
  const head = content.slice(0, 4096);
  const parsed = Papa.parse<Row>(head, { header: true, skipEmptyLines: true });
  const fields = (parsed.meta.fields ?? []).filter(
    (f): f is string => typeof f === "string" && f.length > 0,
  );
  const rows = (parsed.data ?? []).filter(
    (r): r is Row => r != null && typeof r === "object",
  );
  return buildChartSpec(fields, rows).kind !== "none";
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
