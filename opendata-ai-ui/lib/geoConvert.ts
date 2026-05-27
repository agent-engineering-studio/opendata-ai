import { toWgs84 } from "@/lib/geoReproject";

/** Formats we can turn into GeoJSON and draw on a client-side Leaflet map. */
export const GEO_MAP_FORMATS = new Set(["GEOJSON", "TOPOJSON", "KML", "GPX", "GML", "SHP"]);

const _GEO_EXT: [string, string][] = [
  [".geojson", "GEOJSON"],
  [".topojson", "TOPOJSON"],
  [".kml", "KML"],
  [".gpx", "GPX"],
  [".gml", "GML"],
  [".shp", "SHP"],
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

export type GeoJsonObject = Record<string, unknown>;

export type GeoConvert =
  | { status: "ok"; geojson: GeoJsonObject }
  | { status: "unsupported"; reason: string }
  | { status: "error"; reason: string };

type GeoResource = {
  format?: string | null;
  content?: string | null;
  url?: string | null;
  name?: string | null;
};

// The orchestrator caps embedded content; a truncated GeoJSON/KML is invalid and
// must be re-fetched whole from the URL.
function isTruncated(content: string): boolean {
  return /(troncato a \d+ byte|truncated at \d+ bytes|\[…|…\[)/.test(content.slice(-300));
}

function parseJsonGeo(content: string): GeoJsonObject | null {
  const text = content.trim();
  if (!text || (text[0] !== "{" && text[0] !== "[")) return null;
  try {
    const obj = JSON.parse(text) as GeoJsonObject;
    if (obj?.type === "Topology") return null; // TopoJSON handled separately
    return obj;
  } catch {
    return null;
  }
}

/** A multi-layer shapefile zip yields an array of FeatureCollections → merge. */
function mergeCollections(parsed: GeoJsonObject | GeoJsonObject[]): GeoJsonObject {
  if (!Array.isArray(parsed)) return parsed;
  return {
    type: "FeatureCollection",
    features: parsed.flatMap((fc) => ((fc.features as unknown[]) ?? []) as unknown[]),
  };
}

async function proxyText(url: string): Promise<string> {
  const r = await fetch(`/api/proxy?url=${encodeURIComponent(url)}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.text();
}

async function proxyBuffer(url: string): Promise<ArrayBuffer> {
  const r = await fetch(`/api/proxy?url=${encodeURIComponent(url)}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.arrayBuffer();
}

/**
 * Turn a resource into a WGS84 GeoJSON object ready for Leaflet, fetching and
 * converting as needed:
 *   - GeoJSON: inline content when complete, else the full file via the proxy.
 *   - KML/GPX: text → @tmcw/togeojson.
 *   - SHP:     binary → shpjs (the .prj sets the CRS; toWgs84 covers the rest).
 *   - GML / TopoJSON: not supported client-side.
 * Returns null if the resource is not geographic at all (caller skips it).
 */
export async function resourceToGeo(resource: GeoResource): Promise<GeoConvert | null> {
  const fmt = detectGeoFormat(resource.format, resource.content, resource.url || resource.name);
  if (!fmt) return null;

  const inline = (resource.content || "").trim();
  const url = resource.url || undefined;

  try {
    if (fmt === "GML")
      return { status: "unsupported", reason: "formato GML non supportato sulla mappa (apri il file)" };
    if (fmt === "TOPOJSON")
      return { status: "unsupported", reason: "formato TopoJSON non supportato sulla mappa (apri il file)" };

    if (fmt === "SHP") {
      if (!url) return { status: "error", reason: "shapefile senza URL scaricabile" };
      const buf = await proxyBuffer(url);
      const shp = (await import("shpjs")).default;
      const parsed = (await shp(buf)) as unknown as GeoJsonObject | GeoJsonObject[];
      return { status: "ok", geojson: toWgs84(mergeCollections(parsed)) };
    }

    if (fmt === "KML" || fmt === "GPX") {
      const text = inline && !isTruncated(inline) ? inline : url ? await proxyText(url) : "";
      if (!text) return { status: "error", reason: "nessun contenuto da convertire" };
      const tj = await import("@tmcw/togeojson");
      const dom = new DOMParser().parseFromString(text, "text/xml");
      const gj = fmt === "KML" ? tj.kml(dom) : tj.gpx(dom);
      return { status: "ok", geojson: toWgs84(gj as unknown as GeoJsonObject) };
    }

    // GEOJSON (and JSON sniffed as GeoJSON)
    let obj = inline && !isTruncated(inline) ? parseJsonGeo(inline) : null;
    if (!obj && url) obj = parseJsonGeo(await proxyText(url));
    if (!obj && inline) obj = parseJsonGeo(inline); // last resort: try the (maybe truncated) inline
    if (!obj) return { status: "error", reason: "GeoJSON non valido o vuoto" };
    return { status: "ok", geojson: toWgs84(obj) };
  } catch (e) {
    return { status: "error", reason: e instanceof Error ? e.message : String(e) };
  }
}
