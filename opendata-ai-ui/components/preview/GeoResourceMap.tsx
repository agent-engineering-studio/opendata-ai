"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import type { GeoJSON as LeafletGeoJSON, Map as LeafletMap } from "leaflet";
import { useProxyFetch } from "@/lib/useProxyFetch";

/** Formats we can turn into GeoJSON and draw on a client-side Leaflet map. */
export const GEO_MAP_FORMATS = new Set(["GEOJSON", "TOPOJSON", "KML", "GPX", "GML"]);

const _GEO_EXT: [string, string][] = [
  [".geojson", "GEOJSON"],
  [".topojson", "TOPOJSON"],
  [".kml", "KML"],
  [".gpx", "GPX"],
  [".gml", "GML"],
];

/** Detect a geographic resource even when the portal mislabels the format
 *  (e.g. a GeoJSON served as "TXT"/"JSON"). Order: declared format → file
 *  extension in name/url → content sniff (GeoJSON starts with a FeatureCollection
 *  / Feature object). Returns the effective format to render, or null. */
export function detectGeoFormat(
  format?: string | null,
  content?: string | null,
  ref?: string | null,
): string | null {
  const fmt = (format || "").toUpperCase();
  if (GEO_MAP_FORMATS.has(fmt)) return fmt;
  const r = (ref || "").toLowerCase();
  for (const [ext, f] of _GEO_EXT) if (r.includes(ext)) return f;
  const c = (content || "").trimStart();
  if (c.startsWith("{")) {
    const head = c.slice(0, 800);
    if (
      /"type"\s*:\s*"FeatureCollection"/.test(head) ||
      /"type"\s*:\s*"Feature"/.test(head) ||
      /"features"\s*:\s*\[/.test(head)
    )
      return "GEOJSON";
  }
  return null;
}

type GeoJsonObject = Record<string, unknown>;

/** Parse only the JSON family (GeoJSON). KML/GPX are converted async in the
 *  component; GML/TopoJSON are unsupported client-side. */
function parseJsonGeo(content: string): GeoJsonObject | null {
  const text = content.trim();
  if (!text || (text[0] !== "{" && text[0] !== "[")) return null;
  try {
    const obj = JSON.parse(text) as GeoJsonObject;
    if (obj?.type === "Topology") return null; // TopoJSON unsupported
    return obj;
  } catch {
    return null;
  }
}

function MapView({ geojson }: { geojson: GeoJsonObject }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !containerRef.current || mapRef.current) return;
      const map = L.map(containerRef.current, { zoomControl: true }).setView([41.9, 12.5], 5);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(map);
      let layer: LeafletGeoJSON | null = null;
      try {
        layer = L.geoJSON(geojson as never, {
          style: { color: "#2563eb", weight: 2, fillOpacity: 0.35 },
          pointToLayer: (_f, latlng) =>
            L.circleMarker(latlng, { radius: 6, color: "#2563eb", fillColor: "#2563eb", fillOpacity: 0.7 }),
        }).addTo(map);
      } catch {
        /* malformed geometry */
      }
      const b = layer?.getBounds?.();
      if (b && b.isValid()) map.fitBounds(b, { padding: [20, 20], maxZoom: 15 });
      mapRef.current = map;
    })();
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [geojson]);

  return (
    <div
      ref={containerRef}
      className="h-80 w-full overflow-hidden rounded-md border border-slate-200"
    />
  );
}

function MapFromContent({
  content,
  format,
  fallbackUrl,
}: {
  content: string;
  format: string;
  fallbackUrl?: string;
}) {
  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [useFallback, setUseFallback] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const fmt = format.toUpperCase();
      // direct JSON-family (GeoJSON)
      const direct = fmt === "GEOJSON" || fmt === "JSON" ? parseJsonGeo(content) : null;
      if (direct) {
        if (!cancelled) setGeojson(direct);
        return;
      }
      if (fmt === "KML" || fmt === "GPX") {
        try {
          const tj = await import("@tmcw/togeojson");
          const dom = new DOMParser().parseFromString(content, "text/xml");
          const gj = fmt === "KML" ? tj.kml(dom) : tj.gpx(dom);
          if (!cancelled) setGeojson(gj as unknown as GeoJsonObject);
          return;
        } catch {
          if (!cancelled) {
            if (fallbackUrl) setUseFallback(true);
            else setError("conversione non riuscita");
          }
          return;
        }
      }
      // GeoJSON content that didn't parse (often truncated inline) → fetch the
      // full file from the URL if we have one.
      if (!cancelled) {
        if (fallbackUrl) setUseFallback(true);
        else
          setError(
            fmt === "GML" || fmt === "TOPOJSON"
              ? `anteprima mappa non supportata per ${fmt} (apri il file)`
              : "formato non riconosciuto",
          );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [content, format, fallbackUrl]);

  if (useFallback && fallbackUrl) return <LazyMap url={fallbackUrl} format={format} />;
  if (error) return <div className="text-xs text-slate-500">Mappa: {error}.</div>;
  if (!geojson) return <div className="text-xs text-slate-500">Preparazione mappa…</div>;
  return <MapView geojson={geojson} />;
}

function LazyMap({ url, format }: { url: string; format: string }) {
  const decode = useCallback((resp: Response) => resp.text(), []);
  const state = useProxyFetch<string>(url, decode);
  if (state.status === "loading")
    return <div className="text-xs text-slate-500">Caricamento dati geografici…</div>;
  if (state.status === "error")
    return (
      <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
        Impossibile scaricare il file geografico: {state.message}
      </div>
    );
  return <MapFromContent content={state.data} format={format} />;
}

/** Inline client-side map for a geographic resource (GeoJSON/KML/GPX…). */
export function GeoResourceMap({
  content,
  url,
  format,
}: {
  content?: string | null;
  url?: string;
  format: string;
}) {
  const inline = (content || "").trim();
  // The orchestrator caps embedded content; a truncated GeoJSON is invalid JSON,
  // so prefer the full file from the URL and only use inline content when it's complete.
  const truncated = /(troncato a \d+ byte|truncated at \d+ bytes|\[…|…\[)/.test(
    inline.slice(-300),
  );
  if (inline && !truncated)
    return <MapFromContent content={inline} format={format} fallbackUrl={url} />;
  if (url) return <LazyMap url={url} format={format} />;
  if (inline) return <MapFromContent content={inline} format={format} />;
  return null;
}
