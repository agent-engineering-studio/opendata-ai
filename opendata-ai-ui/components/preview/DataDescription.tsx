"use client";

import { useMemo } from "react";
import Papa from "papaparse";
import type { Resource } from "@/lib/types";

type Row = Record<string, string>;

const TIME_RE = /^(time_period|time|date|anno|year|periodo|ref_period)$/i;
const GEO_FORMATS = new Set(["GEOJSON", "SHP", "KML", "KMZ", "GPKG", "WKT", "GML", "TOPOJSON"]);
const _NUM_RE = /^-?\s*\d{1,3}([.,]\d{3})*([.,]\d+)?\s*%?$/;

type Described = {
  kind: string; // short label, e.g. "Serie storica"
  summary: string; // one-line structural description
  geo?: boolean;
};

function isNumericColumn(rows: Row[], field: string): boolean {
  let seen = 0;
  let num = 0;
  for (const r of rows.slice(0, 50)) {
    const v = (r[field] ?? "").trim();
    if (!v) continue;
    seen++;
    if (_NUM_RE.test(v)) num++;
  }
  return seen > 0 && num / seen > 0.8;
}

function describeCsv(content: string): Described | null {
  const parsed = Papa.parse<Row>(content.slice(0, 64_000), {
    header: true,
    skipEmptyLines: true,
  });
  const fields = (parsed.meta.fields ?? []).filter(
    (f): f is string => typeof f === "string" && f.length > 0,
  );
  const rows = (parsed.data ?? []).filter(
    (r): r is Row => r != null && typeof r === "object",
  );
  if (fields.length === 0 || rows.length === 0) return null;

  const nRows = rows.length;
  const timeField = fields.find((f) => TIME_RE.test(f));
  const hasObs = fields.includes("OBS_VALUE");
  const numericFields = fields.filter((f) => isNumericColumn(rows, f));

  // unit of measure, if the SDMX column is present
  const unitField = fields.find((f) => /unit_meas|unità|unit/i.test(f));
  const unit = unitField ? (rows.find((r) => r[unitField])?.[unitField] ?? "") : "";

  // SDMX-style time series
  if (hasObs && timeField) {
    const periods = rows.map((r) => r[timeField]).filter(Boolean).sort();
    const span = periods.length ? ` · periodo ${periods[0]}–${periods[periods.length - 1]}` : "";
    const dims = fields.filter(
      (f) =>
        f !== timeField &&
        f !== "OBS_VALUE" &&
        !/label|note|flag|obs_status|unit_meas/i.test(f) &&
        new Set(rows.map((r) => r[f]).filter(Boolean)).size > 1,
    );
    const dimInfo = dims.length ? ` · disaggregato per ${dims.slice(0, 3).join(", ")}` : "";
    const unitInfo = unit ? ` · unità: ${unit}` : "";
    return {
      kind: "Serie storica",
      summary: `${nRows.toLocaleString("it-IT")} osservazioni${span}${dimInfo}${unitInfo}`,
    };
  }

  // generic time series
  if (timeField && numericFields.length > 0) {
    return {
      kind: "Serie temporale",
      summary: `${nRows.toLocaleString("it-IT")} punti · asse tempo: ${timeField} · ${numericFields.length} serie numeriche`,
    };
  }

  // generic table
  const cols = fields.slice(0, 6).join(", ") + (fields.length > 6 ? "…" : "");
  const numInfo = numericFields.length
    ? ` · ${numericFields.length} colonne numeriche`
    : "";
  return {
    kind: "Dati tabellari",
    summary: `${nRows.toLocaleString("it-IT")} righe × ${fields.length} colonne${numInfo} · colonne: ${cols}`,
  };
}

function describe(resource: Resource): Described | null {
  const fmt = (resource.format || "").toUpperCase();

  if (GEO_FORMATS.has(fmt)) {
    return {
      kind: "Dati geografici",
      summary: `formato ${fmt} — anteprima mappa in arrivo`,
      geo: true,
    };
  }

  if (fmt === "CSV" && resource.content) {
    return describeCsv(resource.content);
  }

  // JSON / GeoJSON handled above for geo; plain JSON gets a light label
  if ((fmt === "JSON" || fmt === "XML" || fmt === "RDF") && resource.content) {
    const lines = resource.content.split("\n").length;
    return { kind: `Documento ${fmt}`, summary: `~${lines.toLocaleString("it-IT")} righe` };
  }

  return null;
}

/** Caption shown above the table/chart describing the kind of data in the resource. */
export function DataDescription({ resource }: { resource: Resource }) {
  const auto = useMemo(() => describe(resource), [resource]);
  const manual = resource.description?.trim();

  if (!auto && !manual) return null;

  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
      {auto ? (
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="font-semibold text-slate-700">{auto.kind}</span>
          <span className="text-slate-500">{auto.summary}</span>
        </div>
      ) : null}
      {manual ? <p className="mt-1 text-slate-600">{manual}</p> : null}
    </div>
  );
}
