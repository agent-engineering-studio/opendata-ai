import { toWgs84 } from "@/lib/geoReproject";
import Papa from "papaparse";

/** Formats we can turn into GeoJSON and draw on a client-side Leaflet map. */
export const GEO_MAP_FORMATS = new Set([
  "GEOJSON", "TOPOJSON", "KML", "GPX", "GML", "SHP", "WMS",
]);

const _GEO_EXT: [string, string][] = [
  [".geojson", "GEOJSON"],
  [".topojson", "TOPOJSON"],
  [".kml", "KML"],
  [".gpx", "GPX"],
  [".gml", "GML"],
  [".shp", "SHP"],
];

// URL substrings that signal a geographic export when the resource has no
// proper extension. Matches opendatasoft `/exports/<fmt>` and CKAN-like
// download paths.
const _GEO_URL_HINTS: [string, string][] = [
  ["/exports/geojson", "GEOJSON"],
  ["/exports/shp", "SHP"],
  ["/exports/kml", "KML"],
  ["/exports/gpx", "GPX"],
  ["/download/geojson", "GEOJSON"],
  ["/download/shp", "SHP"],
  ["format=geojson", "GEOJSON"],
  ["format=shp", "SHP"],
  ["format=kml", "KML"],
];

// Common format aliases that portals use loosely. After toUpperCase() the
// keys match the strings we typically see in CKAN's `format` field and in
// opendatasoft metadata.
const _FORMAT_ALIASES: Record<string, string> = {
  "SHAPEFILE": "SHP",
  "SHAPE": "SHP",
  "ESRI SHAPEFILE": "SHP",
  "GEO+JSON": "GEOJSON",
  "GEO_JSON": "GEOJSON",
  "GEO-JSON": "GEOJSON",
  "TOPO+JSON": "TOPOJSON",
  "WMS_SRVC": "WMS",
  "OGC:WMS": "WMS",
};

/** Detect a geographic resource even when the portal mislabels the format
 *  (e.g. a GeoJSON served as "TXT"/"JSON"). Order: declared format → file
 *  extension in name/url → content sniff (GeoJSON starts with a FeatureCollection
 *  / Feature object). Returns the effective format to render, or null. */
export function detectGeoFormat(
  format?: string | null,
  content?: string | null,
  ref?: string | null,
): string | null {
  const fmt = (format || "").toUpperCase().trim();
  if (GEO_MAP_FORMATS.has(fmt)) return fmt;
  if (fmt in _FORMAT_ALIASES) return _FORMAT_ALIASES[fmt];
  const r = (ref || "").toLowerCase();
  for (const [ext, f] of _GEO_EXT) if (r.includes(ext)) return f;
  for (const [hint, f] of _GEO_URL_HINTS) if (r.includes(hint)) return f;
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

export type WmsLayer = {
  name: string;
  title: string;
  bbox?: [number, number, number, number]; // [westLng, southLat, eastLng, northLat]
};

export type GeoConvert =
  | { status: "ok"; geojson: GeoJsonObject }
  | { status: "wms"; baseUrl: string; layers: WmsLayer[] }
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

/** Options threaded through the conversion to authenticate proxy calls.
 *
 *  Prefer `getToken` for long-running conversion pipelines (the chat stream
 *  can take 60–90s and Clerk JWTs expire fast — a static `token` collected
 *  at the start of the request is likely expired by the time we call the
 *  proxy). Falls back to the static `token` if `getToken` is absent.
 */
export type GeoConvertOptions = {
  token?: string | null;
  getToken?: () => Promise<string | null>;
};

async function proxyText(url: string, opts: GeoConvertOptions = {}): Promise<string> {
  const { proxyFetch } = await import("./api");
  const r = await proxyFetch(url, { token: opts.token, getToken: opts.getToken });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.text();
}

async function proxyBuffer(url: string, opts: GeoConvertOptions = {}): Promise<ArrayBuffer> {
  const { proxyFetch } = await import("./api");
  const r = await proxyFetch(url, { token: opts.token, getToken: opts.getToken });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.arrayBuffer();
}

// ─── WMS support ──────────────────────────────────────────────────────────────

const _wmsCache = new Map<string, Promise<WmsLayer[]>>();

function wmsCapsUrl(baseUrl: string): string {
  const sep = baseUrl.includes("?") ? "&" : "?";
  return `${baseUrl}${sep}service=WMS&request=GetCapabilities`;
}

function directChild(parent: Element, tag: string): Element | null {
  for (const child of Array.from(parent.children)) {
    if (child.tagName === tag || child.tagName.endsWith(`:${tag}`)) return child;
  }
  return null;
}

/** Best-effort GetCapabilities parser. Returns named, leaf-ish layers (capped). */
async function discoverWmsLayers(
  baseUrl: string,
  opts: GeoConvertOptions = {},
): Promise<WmsLayer[]> {
  let cached = _wmsCache.get(baseUrl);
  if (!cached) {
    cached = (async () => {
      const xml = await proxyText(wmsCapsUrl(baseUrl), opts);
      const doc = new DOMParser().parseFromString(xml, "application/xml");
      if (doc.getElementsByTagName("parsererror").length > 0) return [];
      const out: WmsLayer[] = [];
      const allLayers = doc.getElementsByTagName("Layer");
      for (const layer of Array.from(allLayers)) {
        if (out.length >= 10) break;
        const nameEl = directChild(layer, "Name");
        const name = nameEl?.textContent?.trim();
        if (!name) continue; // group layers w/o Name → skip
        const titleEl = directChild(layer, "Title");
        const title = titleEl?.textContent?.trim() || name;
        let bbox: WmsLayer["bbox"];
        const exBbox = layer.getElementsByTagName("EX_GeographicBoundingBox")[0];
        if (exBbox) {
          const w = parseFloat(exBbox.getElementsByTagName("westBoundLongitude")[0]?.textContent || "");
          const s = parseFloat(exBbox.getElementsByTagName("southBoundLatitude")[0]?.textContent || "");
          const e = parseFloat(exBbox.getElementsByTagName("eastBoundLongitude")[0]?.textContent || "");
          const n = parseFloat(exBbox.getElementsByTagName("northBoundLatitude")[0]?.textContent || "");
          if ([w, s, e, n].every((v) => Number.isFinite(v))) bbox = [w, s, e, n];
        }
        if (!bbox) {
          // WMS 1.1: <LatLonBoundingBox minx=... miny=... maxx=... maxy=.../>
          const llbb = layer.getElementsByTagName("LatLonBoundingBox")[0];
          if (llbb) {
            const w = parseFloat(llbb.getAttribute("minx") || "");
            const s = parseFloat(llbb.getAttribute("miny") || "");
            const e = parseFloat(llbb.getAttribute("maxx") || "");
            const n = parseFloat(llbb.getAttribute("maxy") || "");
            if ([w, s, e, n].every((v) => Number.isFinite(v))) bbox = [w, s, e, n];
          }
        }
        out.push({ name, title, bbox });
      }
      return out;
    })().catch(() => []);
    _wmsCache.set(baseUrl, cached);
  }
  return cached;
}

// ─── CSV-with-WKT support ─────────────────────────────────────────────────────

const _WKT_HEADERS = /^(geom|geometry|wkt|the_geom|shape|geo|wkt_geom)$/i;
const _WKT_TYPES = /^\s*(?:SRID=\d+;\s*)?(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\b/i;

function splitTopLevel(s: string): string[] {
  const parts: string[] = [];
  let depth = 0, start = 0;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === "(") depth++;
    else if (c === ")") depth--;
    else if (c === "," && depth === 0) {
      parts.push(s.slice(start, i).trim());
      start = i + 1;
    }
  }
  parts.push(s.slice(start).trim());
  return parts;
}

function parsePointPair(s: string): [number, number] | null {
  const nums = s.trim().split(/\s+/).map(Number).filter((n) => Number.isFinite(n));
  return nums.length >= 2 ? [nums[0], nums[1]] : null;
}

function parsePointList(s: string): [number, number][] {
  return splitTopLevel(s).map(parsePointPair).filter((p): p is [number, number] => p != null);
}

function stripOuter(s: string): string {
  const t = s.trim();
  return t.startsWith("(") && t.endsWith(")") ? t.slice(1, -1).trim() : t;
}

/** Minimal WKT → GeoJSON geometry. Handles 2D POINT/LINESTRING/POLYGON and
 *  their MULTI variants. Returns null on unrecognised input. */
export function wktToGeometry(raw: string): GeoJsonObject | null {
  const wkt = raw.trim().replace(/^SRID=\d+;\s*/i, "");
  const m = wkt.match(/^([A-Za-z]+)\s*(?:Z|M|ZM)?\s*\((.*)\)\s*$/s);
  if (!m) return null;
  const type = m[1].toUpperCase();
  const body = m[2].trim();
  switch (type) {
    case "POINT": {
      const c = parsePointPair(body);
      return c ? { type: "Point", coordinates: c } : null;
    }
    case "LINESTRING":
      return { type: "LineString", coordinates: parsePointList(body) };
    case "MULTIPOINT": {
      const parts = splitTopLevel(body).map((p) => parsePointPair(stripOuter(p)));
      return { type: "MultiPoint", coordinates: parts.filter((p): p is [number, number] => p != null) };
    }
    case "POLYGON":
      return {
        type: "Polygon",
        coordinates: splitTopLevel(body).map((r) => parsePointList(stripOuter(r))),
      };
    case "MULTILINESTRING":
      return {
        type: "MultiLineString",
        coordinates: splitTopLevel(body).map((r) => parsePointList(stripOuter(r))),
      };
    case "MULTIPOLYGON":
      return {
        type: "MultiPolygon",
        coordinates: splitTopLevel(body).map((poly) =>
          splitTopLevel(stripOuter(poly)).map((r) => parsePointList(stripOuter(r))),
        ),
      };
    default:
      return null;
  }
}

/** Convert CSV text to a GeoJSON FeatureCollection iff a WKT geometry column
 *  is detected; returns null when the CSV has no spatial column. */
function csvWktToGeoJson(csv: string): GeoJsonObject | null {
  const result = Papa.parse<Record<string, string>>(csv, {
    header: true,
    skipEmptyLines: true,
    dynamicTyping: false,
  });
  const rows = result.data;
  if (!rows.length) return null;
  const headers = result.meta.fields || Object.keys(rows[0]);
  if (!headers.length) return null;

  // Pick the WKT column: prefer a header that matches the name pattern, then
  // any column whose first non-empty value parses as a WKT geometry.
  const sampleSize = Math.min(rows.length, 5);
  const nameMatch = headers.find((h) => _WKT_HEADERS.test(h));
  let wktCol: string | null = nameMatch || null;
  if (!wktCol) {
    for (const h of headers) {
      let hits = 0;
      for (let i = 0; i < sampleSize; i++) {
        const v = (rows[i][h] || "").trim();
        if (v && _WKT_TYPES.test(v)) hits++;
      }
      if (hits >= 1) {
        wktCol = h;
        break;
      }
    }
  }
  if (!wktCol) return null;

  const features: GeoJsonObject[] = [];
  for (const row of rows) {
    const wkt = (row[wktCol] || "").trim();
    if (!wkt) continue;
    const geom = wktToGeometry(wkt);
    if (!geom) continue;
    const properties: Record<string, unknown> = {};
    for (const h of headers) if (h !== wktCol) properties[h] = row[h];
    features.push({ type: "Feature", geometry: geom, properties });
  }
  if (!features.length) return null;
  return { type: "FeatureCollection", features };
}

/** True when a resource is a ZIP/KMZ archive, by declared format or extension. */
export function isZip(format?: string | null, ref?: string | null): boolean {
  const f = (format || "").toUpperCase();
  if (f === "ZIP" || f === "KMZ") return true;
  const r = (ref || "").toLowerCase();
  return /\.(zip|kmz)(?:$|\?)/.test(r);
}

function _entryExt(name: string): string {
  const base = name.split("/").pop() || name;
  const i = base.lastIndexOf(".");
  return i >= 0 ? base.slice(i + 1).toLowerCase() : "";
}

function _isJunk(name: string): boolean {
  return name.startsWith("__MACOSX/") || name.endsWith("/.DS_Store") || name.endsWith("/Thumbs.db");
}

/** Open a zip resource and return geographic content if recognisable: a
 *  shapefile bundle (.shp+.dbf, passed whole to shpjs) or a KMZ (single .kml).
 *  Returns null when the zip carries no map-renderable layer; ZipPreview will
 *  handle the per-entry case for non-geo archives.
 */
async function unzipForGeo(buf: ArrayBuffer): Promise<GeoConvert> {
  const JSZip = (await import("jszip")).default;
  const zip = await JSZip.loadAsync(buf);
  const names = Object.keys(zip.files).filter((n) => !zip.files[n].dir && !_isJunk(n));
  const exts = new Set(names.map(_entryExt));

  // Shapefile bundle → shpjs handles the zip ArrayBuffer directly. Some
  // portals omit .dbf or only ship .shp; shpjs tolerates that, so we accept
  // any zip containing a .shp entry and let the library do the heavy lifting.
  if (exts.has("shp")) {
    try {
      const shp = (await import("shpjs")).default;
      const parsed = (await shp(buf)) as unknown as GeoJsonObject | GeoJsonObject[];
      return { status: "ok", geojson: toWgs84(mergeCollections(parsed)) };
    } catch (e) {
      const reason = e instanceof Error ? e.message : String(e);
      // eslint-disable-next-line no-console
      console.warn("[geoConvert] shapefile zip parse failed:", reason, { names });
      return { status: "error", reason: `shapefile non leggibile: ${reason}` };
    }
  }

  // KMZ → a .kml entry (usually doc.kml) inside a zip.
  const kmlName = names.find((n) => _entryExt(n) === "kml");
  if (kmlName) {
    try {
      const text = await zip.files[kmlName].async("string");
      const tj = await import("@tmcw/togeojson");
      const dom = new DOMParser().parseFromString(text, "text/xml");
      return { status: "ok", geojson: toWgs84(tj.kml(dom) as unknown as GeoJsonObject) };
    } catch (e) {
      const reason = e instanceof Error ? e.message : String(e);
      // eslint-disable-next-line no-console
      console.warn("[geoConvert] kmz parse failed:", reason);
      return { status: "error", reason: `KMZ non leggibile: ${reason}` };
    }
  }

  // Also detect geojson/topojson/gpx entries inside a zip (some portals
  // ship GeoJSON wrapped in a zip).
  const geojsonEntry = names.find((n) => _entryExt(n) === "geojson");
  if (geojsonEntry) {
    try {
      const text = await zip.files[geojsonEntry].async("string");
      const obj = parseJsonGeo(text);
      if (!obj) return { status: "error", reason: "GeoJSON nello zip non valido" };
      return { status: "ok", geojson: toWgs84(obj) };
    } catch (e) {
      const reason = e instanceof Error ? e.message : String(e);
      // eslint-disable-next-line no-console
      console.warn("[geoConvert] geojson-in-zip parse failed:", reason);
      return { status: "error", reason: `GeoJSON nello zip non leggibile: ${reason}` };
    }
  }

  // eslint-disable-next-line no-console
  console.warn("[geoConvert] zip without recognised geo entries:", {
    names,
    exts: Array.from(exts),
  });
  return {
    status: "unsupported",
    reason: `archivio senza file geografici riconoscibili (estensioni viste: ${Array.from(exts).join(", ") || "nessuna"})`,
  };
}

/**
 * Turn a resource into a WGS84 GeoJSON object ready for Leaflet, fetching and
 * converting as needed:
 *   - GeoJSON: inline content when complete, else the full file via the proxy.
 *   - KML/GPX: text → @tmcw/togeojson.
 *   - SHP:     binary → shpjs (the .prj sets the CRS; toWgs84 covers the rest).
 *   - ZIP/KMZ: shapefile bundle → shpjs; KMZ → extract .kml → togeojson.
 *   - WMS:     GetCapabilities → list of layers (rendered as L.tileLayer.wms).
 *   - CSV:     parsed for a WKT geometry column (e.g. confinicomunalilazio.csv).
 *   - GML / TopoJSON: not supported client-side.
 * Returns null if the resource is not geographic at all (caller skips it).
 */
export async function resourceToGeo(
  resource: GeoResource,
  opts: GeoConvertOptions = {},
): Promise<GeoConvert | null> {
  // ZIP / KMZ: detect before the format gate — many portals label shapefile
  // bundles as "ZIP" so detectGeoFormat would (correctly) miss them.
  if (isZip(resource.format, resource.url || resource.name)) {
    const url = resource.url || undefined;
    if (!url) return null;
    try {
      return await unzipForGeo(await proxyBuffer(url, opts));
    } catch (e) {
      return { status: "error", reason: e instanceof Error ? e.message : String(e) };
    }
  }

  const fmt = detectGeoFormat(resource.format, resource.content, resource.url || resource.name);
  const inline = (resource.content || "").trim();
  const url = resource.url || undefined;

  // Last-resort path: a CSV whose declared/sniffed format isn't geo, but which
  // carries a WKT geometry column. We must check BEFORE returning null, because
  // detectGeoFormat() correctly rejects CSV.
  if (!fmt) {
    const declared = (resource.format || "").toUpperCase();
    const isCsv = declared === "CSV" || /\.csv(?:$|\?)/i.test(url || "");
    if (!isCsv) return null;
    try {
      const csv = inline && !isTruncated(inline) ? inline : url ? await proxyText(url, opts) : "";
      if (!csv) return null;
      const geo = csvWktToGeoJson(csv);
      if (!geo) return null;
      return { status: "ok", geojson: toWgs84(geo) };
    } catch (e) {
      return { status: "error", reason: e instanceof Error ? e.message : String(e) };
    }
  }

  try {
    if (fmt === "GML")
      return { status: "unsupported", reason: "formato GML non supportato sulla mappa (apri il file)" };
    if (fmt === "TOPOJSON")
      return { status: "unsupported", reason: "formato TopoJSON non supportato sulla mappa (apri il file)" };

    if (fmt === "WMS") {
      if (!url) return { status: "error", reason: "WMS senza URL" };
      const baseUrl = url.split("?")[0];
      const layers = await discoverWmsLayers(baseUrl, opts);
      if (!layers.length) return { status: "error", reason: "nessun layer WMS pubblicato" };
      return { status: "wms", baseUrl, layers };
    }

    if (fmt === "SHP") {
      if (!url) return { status: "error", reason: "shapefile senza URL scaricabile" };
      const buf = await proxyBuffer(url, opts);
      const shp = (await import("shpjs")).default;
      const parsed = (await shp(buf)) as unknown as GeoJsonObject | GeoJsonObject[];
      return { status: "ok", geojson: toWgs84(mergeCollections(parsed)) };
    }

    if (fmt === "KML" || fmt === "GPX") {
      // Prefer the FULL file from the URL: inline content is capped server-side
      // (~200 KB), so it's usually a truncated sample that would draw only part
      // of the geometry. Fall back to inline only when there's no URL.
      let text = "";
      if (url) {
        try {
          text = await proxyText(url, opts);
        } catch {
          text = "";
        }
      }
      if (!text && inline) text = inline;
      if (!text) return { status: "error", reason: "nessun contenuto da convertire" };
      const tj = await import("@tmcw/togeojson");
      const dom = new DOMParser().parseFromString(text, "text/xml");
      const gj = fmt === "KML" ? tj.kml(dom) : tj.gpx(dom);
      return { status: "ok", geojson: toWgs84(gj as unknown as GeoJsonObject) };
    }

    // GEOJSON (and JSON sniffed as GeoJSON). Prefer the FULL file from the URL —
    // the inline `content` is capped at ~200 KB server-side, so a large dataset
    // (e.g. 1128 bike-path features ≈ 714 KB) arrives truncated and would render
    // as a single partial line. Inline is only the fallback when there's no URL.
    let obj: GeoJsonObject | null = null;
    if (url) {
      try {
        obj = parseJsonGeo(await proxyText(url, opts));
      } catch {
        obj = null;
      }
    }
    if (!obj && inline) obj = parseJsonGeo(inline);
    if (!obj) return { status: "error", reason: "GeoJSON non valido o vuoto" };
    return { status: "ok", geojson: toWgs84(obj) };
  } catch (e) {
    return { status: "error", reason: e instanceof Error ? e.message : String(e) };
  }
}
