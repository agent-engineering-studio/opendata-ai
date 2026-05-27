"use client";

/**
 * Renders a self-contained Leaflet+OSM HTML map (produced by osm-mcp) inside a
 * sandboxed iframe via srcDoc. `allow-scripts` is required for Leaflet to run;
 * we deliberately omit `allow-same-origin` so the embedded document cannot
 * touch the parent page / cookies.
 */
export function MapEmbed({ html, height = 320 }: { html: string; height?: number }) {
  return (
    <iframe
      title="Mappa OSM"
      srcDoc={html}
      sandbox="allow-scripts"
      className="w-full rounded-md border border-slate-200"
      style={{ height }}
      loading="lazy"
    />
  );
}
