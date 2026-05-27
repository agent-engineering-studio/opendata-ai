"use client";

import { useState } from "react";
import type { Resource } from "@/lib/types";
import { ResourcePreview, isPreviewable } from "./preview/ResourcePreview";
import { CsvTablePreview } from "./preview/CsvTablePreview";
import { ChartPreview, isChartable } from "./preview/ChartPreview";
import { DataDescription } from "./preview/DataDescription";
import { MapEmbed } from "./preview/MapEmbed";
import { GeoResourceMap, GEO_MAP_FORMATS } from "./preview/GeoResourceMap";

function formatBadgeColor(format: string): string {
  const f = format.toUpperCase();
  if (["CSV", "JSON", "XLSX", "XLS"].includes(f))
    return "bg-blue-100 text-blue-800";
  if (["GEOJSON", "SHP", "KML", "WMS", "GPKG"].includes(f))
    return "bg-emerald-100 text-emerald-800";
  return "bg-slate-100 text-slate-700";
}

function sourceBadgeColor(source: string): string {
  if (source === "ckan") return "bg-violet-100 text-violet-800";
  if (source === "istat") return "bg-amber-100 text-amber-800";
  if (source === "eurostat") return "bg-sky-100 text-sky-800";
  if (source === "oecd") return "bg-rose-100 text-rose-800";
  return "bg-slate-100 text-slate-700";
}

function sourceTooltip(source: string): string {
  if (source === "ckan") return "Portale CKAN (open data)";
  if (source === "istat") return "ISTAT — statistica ufficiale italiana (SDMX)";
  if (source === "eurostat") return "Eurostat — statistica UE (SDMX)";
  if (source === "oecd") return "OCSE / OECD — statistica internazionale (SDMX)";
  return source;
}

export function ResourceCard({ resource }: { resource: Resource }) {
  const [expanded, setExpanded] = useState(false);
  const [view, setView] = useState<"table" | "chart">("table");
  const display = resource.name || resource.url || "(senza nome)";
  const badge = resource.format?.trim() ? resource.format.toUpperCase() : "—";
  const hasMap = !!resource.preview_html;
  const isGeo = GEO_MAP_FORMATS.has((resource.format || "").toUpperCase());
  const canPreview =
    hasMap ||
    (isGeo && (!!resource.content || !!resource.url)) ||
    isPreviewable(resource.format, resource.content, resource.url);
  const isCsv = resource.format?.toUpperCase() === "CSV";
  // Offer the chart toggle when we have chartable inline content, or when the
  // CSV will be lazily fetched (no inline content but a URL is present).
  const canChart =
    isCsv &&
    (isChartable(resource.content) || (!resource.content && !!resource.url));

  return (
    <div className="rounded-md border border-slate-200 bg-white">
      <div className="flex items-center gap-3 px-3 py-2">
        <span
          className={`inline-flex min-w-[3.5rem] justify-center rounded px-2 py-0.5 font-mono text-xs ${formatBadgeColor(badge)}`}
        >
          {badge}
        </span>
        {resource.source ? (
          <span
            className={`inline-flex justify-center rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${sourceBadgeColor(resource.source)}`}
            title={sourceTooltip(resource.source)}
          >
            {resource.source}
          </span>
        ) : null}
        <span className="flex-1 truncate text-sm text-slate-800">{display}</span>
        {resource.url ? (
          <a
            href={resource.url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-sm font-medium text-blue-700 hover:text-blue-900"
          >
            → Apri
          </a>
        ) : null}
      </div>

      {canPreview ? (
        <div className="border-t border-slate-100 px-3 py-1.5">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-xs font-medium text-slate-600 hover:text-slate-900"
            aria-expanded={expanded}
          >
            {expanded ? "▾ Nascondi anteprima" : "▸ Mostra anteprima"}
          </button>
          {expanded ? (
            <div className="mt-2 space-y-2">
              <DataDescription resource={resource} />
              {hasMap ? (
                <MapEmbed html={resource.preview_html as string} />
              ) : isGeo ? (
                <GeoResourceMap
                  content={resource.content}
                  url={resource.url}
                  format={resource.format}
                />
              ) : (
                <>
                  {canChart ? (
                    <div className="inline-flex overflow-hidden rounded border border-slate-300 text-xs">
                      <button
                        type="button"
                        onClick={() => setView("table")}
                        className={`px-2.5 py-1 ${view === "table" ? "bg-slate-800 text-white" : "bg-white text-slate-700 hover:bg-slate-50"}`}
                      >
                        Tabella
                      </button>
                      <button
                        type="button"
                        onClick={() => setView("chart")}
                        className={`px-2.5 py-1 ${view === "chart" ? "bg-slate-800 text-white" : "bg-white text-slate-700 hover:bg-slate-50"}`}
                      >
                        Grafico
                      </button>
                    </div>
                  ) : null}
                  {canChart && view === "chart" ? (
                    <ChartPreview content={resource.content} url={resource.url} />
                  ) : canChart ? (
                    <CsvTablePreview content={resource.content} url={resource.url} />
                  ) : (
                    <ResourcePreview
                      format={resource.format}
                      content={resource.content}
                      url={resource.url}
                    />
                  )}
                </>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
