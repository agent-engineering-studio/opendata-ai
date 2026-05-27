"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import type {
  GeoJSON as LeafletGeoJSON,
  Map as LeafletMap,
} from "leaflet";

export type GeoLayer = {
  id: string;
  name: string;
  geojson: unknown; // GeoJSON FeatureCollection / Feature / Geometry
  color: string;
  visible: boolean;
};

/**
 * Persistent client-side Leaflet map (OSM tiles) that renders the given GeoJSON
 * layers. Adding/removing layers across chat turns keeps the same map instance
 * (a "Google Maps for geographic open data"). On layer changes it fits the view
 * to the union of all visible layers.
 */
export function GeoMap({ layers }: { layers: GeoLayer[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  // id → Leaflet layer, so we can add/remove incrementally.
  const layerObjsRef = useRef<Map<string, LeafletGeoJSON>>(new Map());

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
      const wanted = new Set(layers.filter((l) => l.visible).map((l) => l.id));

      // Remove layers no longer present or hidden.
      for (const [id, obj] of objs) {
        if (!wanted.has(id)) {
          map.removeLayer(obj);
          objs.delete(id);
        }
      }

      // Add new visible layers.
      for (const layer of layers) {
        if (!layer.visible || objs.has(layer.id)) continue;
        try {
          const gj = L.geoJSON(layer.geojson as never, {
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
          // skip malformed GeoJSON
        }
      }

      // Fit to the union of all visible layers.
      if (objs.size > 0) {
        let bounds: ReturnType<LeafletGeoJSON["getBounds"]> | null = null;
        for (const obj of objs.values()) {
          const b = obj.getBounds?.();
          if (b && b.isValid()) bounds = bounds ? bounds.extend(b) : b;
        }
        if (bounds && bounds.isValid()) {
          map.fitBounds(bounds, { padding: [24, 24], maxZoom: 14 });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [layers]);

  return <div ref={containerRef} className="h-full w-full" />;
}
