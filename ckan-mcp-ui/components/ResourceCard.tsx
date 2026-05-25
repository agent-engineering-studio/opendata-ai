"use client";

import { useState } from "react";
import type { Resource } from "@/lib/types";
import { ResourcePreview, isPreviewable } from "./preview/ResourcePreview";

function formatBadgeColor(format: string): string {
  const f = format.toUpperCase();
  if (["CSV", "JSON", "XLSX", "XLS"].includes(f))
    return "bg-blue-100 text-blue-800";
  if (["GEOJSON", "SHP", "KML", "WMS", "GPKG"].includes(f))
    return "bg-emerald-100 text-emerald-800";
  return "bg-slate-100 text-slate-700";
}

export function ResourceCard({ resource }: { resource: Resource }) {
  const [expanded, setExpanded] = useState(false);
  const display = resource.name || resource.url || "(senza nome)";
  const badge = resource.format?.trim() ? resource.format.toUpperCase() : "—";
  const canPreview = isPreviewable(resource.format, resource.content);

  return (
    <div className="rounded-md border border-slate-200 bg-white">
      <div className="flex items-center gap-3 px-3 py-2">
        <span
          className={`inline-flex min-w-[3.5rem] justify-center rounded px-2 py-0.5 font-mono text-xs ${formatBadgeColor(badge)}`}
        >
          {badge}
        </span>
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
            <div className="mt-2">
              <ResourcePreview
                format={resource.format}
                content={resource.content as string}
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
