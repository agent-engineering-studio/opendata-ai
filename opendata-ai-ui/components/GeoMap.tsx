"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import type {
  GeoJSON as LeafletGeoJSON,
  LatLngBounds,
  Layer as LeafletLayer,
  Map as LeafletMap,
} from "leaflet";
import { toWgs84 } from "@/lib/geoReproject";

export type GeoLayer = {
  id: string;
  name: string;
  geojson: unknown | null; // null when the resource is geographic but not mappable
  // WMS layers are rendered as tile overlays instead of vector. baseUrl is the
  // GetMap endpoint, layerName comes from GetCapabilities, bbox (if known)
  // drives the initial fit.
  wms?: { baseUrl: string; layerName: string; bbox?: [number, number, number, number] };
  color: string;
  visible: boolean;
  error?: string; // reason the layer can't be drawn (GML/TopoJSON, fetch failure…)
};

/**
 * Persistent client-side Leaflet map (OSM tiles) that renders the given GeoJSON
 * layers. Adding/removing layers across chat turns keeps the same map instance
 * (a "Google Maps for geographic open data").
 *
 * Fit behaviour:
 *   - `focusLayerIds` set → fit to ONLY those layers (typically the layers
 *     just added by the most recent chat turn). This keeps the viewport on
 *     the user's latest question instead of zooming out to a regional
 *     average that hides everything.
 *   - `focusLayerIds` empty/undefined → fit to the union of all visible
 *     layers (use case: explicit "Vista globale" button).
 *
 * `focusKey` is a counter the parent can bump (with the same `focusLayerIds`)
 * to force a re-fit even when the ID set didn't change.
 */
export function GeoMap({
  layers,
  focusLayerIds,
  focusKey,
}: {
  layers: GeoLayer[];
  focusLayerIds?: string[];
  focusKey?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  // id → Leaflet layer (GeoJSON or TileLayer.WMS), so we can add/remove incrementally.
  const layerObjsRef = useRef<Map<string, LeafletLayer>>(new Map());

  // Initialise the map once.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !containerRef.current || mapRef.current) return;
      const map = L.map(containerRef.current, { zoomControl: true }).setView(
        [41.9, 12.5], // Italy
        5,
      );
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(map);
      mapRef.current = map;
    })();
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      layerObjsRef.current.clear();
    };
  }, []);

  // Sync layers whenever the list changes.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      const map = mapRef.current;
      if (cancelled || !map) return;

      const objs = layerObjsRef.current;
      const isMappable = (l: GeoLayer) => l.geojson != null || l.wms != null;
      const wanted = new Set(
        layers.filter((l) => l.visible && isMappable(l)).map((l) => l.id),
      );

      // Remove layers no longer present or hidden.
      for (const [id, obj] of objs) {
        if (!wanted.has(id)) {
          map.removeLayer(obj);
          objs.delete(id);
        }
      }

      // Add new visible layers.
      for (const layer of layers) {
        if (!layer.visible || !isMappable(layer) || objs.has(layer.id)) continue;
        try {
          if (layer.wms) {
            const tl = L.tileLayer.wms(layer.wms.baseUrl, {
              layers: layer.wms.layerName,
              format: "image/png",
              transparent: true,
              opacity: 0.65,
              version: "1.3.0",
            });
            tl.addTo(map);
            objs.set(layer.id, tl);
            continue;
          }
          const wgs84 = toWgs84(layer.geojson as Record<string, unknown>);
          const gj = L.geoJSON(wgs84 as never, {
            style: { color: layer.color, weight: 2, fillOpacity: 0.35 },
            pointToLayer: (_f, latlng) =>
              L.circleMarker(latlng, {
                radius: 6,
                color: layer.color,
                fillColor: layer.color,
                fillOpacity: 0.7,
              }),
          });
          gj.addTo(map);
          objs.set(layer.id, gj);
        } catch {
          // skip malformed GeoJSON / unreachable WMS
        }
      }

      // Fit to either the focused subset (latest batch) or the union of all
      // visible layers. Vector layers expose getBounds(); WMS tile layers
      // don't, so use their advertised bbox when present.
      const focus = focusLayerIds && focusLayerIds.length > 0
        ? new Set(focusLayerIds)
        : null;
      let bounds: LatLngBounds | null = null;
      for (const layer of layers) {
        if (!objs.has(layer.id)) continue;
        if (focus && !focus.has(layer.id)) continue;
        if (layer.wms?.bbox) {
          const [w, s, e, n] = layer.wms.bbox;
          if ([w, s, e, n].every((v) => Number.isFinite(v))) {
            const b = L.latLngBounds([s, w], [n, e]);
            bounds = bounds ? bounds.extend(b) : b;
          }
          continue;
        }
        const obj = objs.get(layer.id) as LeafletGeoJSON | undefined;
        const b = obj?.getBounds?.();
        if (b && b.isValid()) bounds = bounds ? bounds.extend(b) : b;
      }
      if (bounds && bounds.isValid()) {
        map.fitBounds(bounds, { padding: [24, 24], maxZoom: 14 });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [layers, focusLayerIds, focusKey]);

  return <div ref={containerRef} className="h-full w-full" />;
}
