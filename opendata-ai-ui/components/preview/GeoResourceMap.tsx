"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import type { GeoJSON as LeafletGeoJSON, Map as LeafletMap } from "leaflet";
import { useAuth } from "@/lib/auth";
import { toWgs84 } from "@/lib/geoReproject";
import {
  GEO_MAP_FORMATS,
  detectGeoFormat,
  resourceToGeo,
  type GeoJsonObject,
} from "@/lib/geoConvert";

// Re-exported so existing imports (ResourceCard) keep working unchanged.
export { GEO_MAP_FORMATS, detectGeoFormat };

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
        const wgs84 = toWgs84(geojson);
        layer = L.geoJSON(wgs84 as never, {
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

type State =
  | { status: "loading" }
  | { status: "ok"; geojson: GeoJsonObject }
  | { status: "message"; text: string };

/** Inline client-side map for a geographic resource (GeoJSON/KML/GPX/SHP…). */
export function GeoResourceMap({
  content,
  url,
  format,
}: {
  content?: string | null;
  url?: string;
  format: string;
}) {
  const [state, setState] = useState<State>({ status: "loading" });
  const { getToken } = useAuth();

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    (async () => {
      const res = await resourceToGeo(
        { format, content, url, name: url },
        { getToken },
      );
      if (cancelled) return;
      if (!res) setState({ status: "message", text: "formato non riconosciuto" });
      else if (res.status === "ok") setState({ status: "ok", geojson: res.geojson });
      else if (res.status === "wms")
        setState({
          status: "message",
          text: "WMS — disponibile come layer nella pagina /esplora",
        });
      else setState({ status: "message", text: res.reason });
    })();
    return () => {
      cancelled = true;
    };
  }, [content, url, format, getToken]);

  if (state.status === "loading")
    return <div className="text-xs text-slate-500">Preparazione mappa…</div>;
  if (state.status === "message")
    return <div className="text-xs text-slate-500">Mappa: {state.text}.</div>;
  return <MapView geojson={state.geojson} />;
}
