"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import type { GeoJSON as LeafletGeoJSON, Map as LeafletMap } from "leaflet";
import { useProxyFetch } from "@/lib/useProxyFetch";

/** Formats we can turn into GeoJSON and draw on a client-side Leaflet map. */
export const GEO_MAP_FORMATS = new Set(["GEOJSON", "TOPOJSON", "KML", "GPX", "GML"]);

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

function MapFromContent({ content, format }: { content: string; format: string }) {
  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          if (!cancelled) setError("conversione non riuscita");
          return;
        }
      }
      if (!cancelled)
        setError(
          fmt === "GML" || fmt === "TOPOJSON"
            ? `anteprima mappa non supportata per ${fmt} (apri il file)`
            : "formato non riconosciuto",
        );
    })();
    return () => {
      cancelled = true;
    };
  }, [content, format]);

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
  if (content && content.trim().length > 0)
    return <MapFromContent content={content} format={format} />;
  if (url) return <LazyMap url={url} format={format} />;
  return null;
}
