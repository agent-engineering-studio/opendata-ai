import proj4 from "proj4";

/**
 * Leaflet draws GeoJSON assuming WGS84 (EPSG:4326, lon/lat degrees). Many Italian
 * open-data files are in a projected CRS (UTM 32/33N, Monte Mario / Gauss-Boaga,
 * Web Mercator) with coordinates in metres → Leaflet places them off the map and
 * nothing is visible. This reprojects a GeoJSON object to WGS84 in place-ish
 * (returns a new geometry tree), based on its declared `crs` member, with a
 * heuristic fallback when coordinates are clearly not lon/lat.
 */

// Common CRS used by Italian / EU portals. proj4 only knows 4326 + 3857 natively.
const DEFS: Record<string, string> = {
  "EPSG:3857": "+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +no_defs",
  "EPSG:32632": "+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs",
  "EPSG:32633": "+proj=utm +zone=33 +datum=WGS84 +units=m +no_defs",
  "EPSG:25832": "+proj=utm +zone=32 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs",
  "EPSG:25833": "+proj=utm +zone=33 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs",
  "EPSG:23032": "+proj=utm +zone=32 +ellps=intl +towgs84=-87,-98,-121,0,0,0,0 +units=m +no_defs",
  "EPSG:3003": "+proj=tmerc +lat_0=0 +lon_0=9 +k=0.9996 +x_0=1500000 +y_0=0 +ellps=intl +towgs84=-104.1,-49.1,-9.9,0.971,-2.917,0.714,-11.68 +units=m +no_defs",
  "EPSG:3004": "+proj=tmerc +lat_0=0 +lon_0=15 +k=0.9996 +x_0=2520000 +y_0=0 +ellps=intl +towgs84=-104.1,-49.1,-9.9,0.971,-2.917,0.714,-11.68 +units=m +no_defs",
};

const WGS84 = ["EPSG:4326", "CRS84", "OGC:1.3:CRS84", "URN:OGC:DEF:CRS:OGC:1.3:CRS84"];

function epsgFromCrsName(name: unknown): string | null {
  if (typeof name !== "string") return null;
  const m = name.toUpperCase().match(/EPSG:*:?(\d{3,6})/);
  if (m) return `EPSG:${m[1]}`;
  if (name.toUpperCase().includes("CRS84")) return "EPSG:4326";
  return null;
}

type AnyGeo = Record<string, unknown>;

function transformCoords(coords: unknown, fn: (xy: number[]) => number[]): unknown {
  if (!Array.isArray(coords)) return coords;
  // leaf position [x, y, (z)]
  if (typeof coords[0] === "number" && typeof coords[1] === "number") {
    return fn(coords as number[]);
  }
  return coords.map((c) => transformCoords(c, fn));
}

function sampleCoord(geojson: AnyGeo): number[] | null {
  let found: number[] | null = null;
  const visit = (c: unknown): void => {
    if (found || !Array.isArray(c)) return;
    if (typeof c[0] === "number" && typeof c[1] === "number") {
      found = c as number[];
      return;
    }
    for (const x of c) visit(x);
  };
  const feats = (geojson.features as AnyGeo[]) ?? [geojson];
  for (const f of feats) {
    const g = (f.geometry as AnyGeo) ?? f;
    visit(g?.coordinates);
    if (found) break;
  }
  return found;
}

function isLonLat(xy: number[]): boolean {
  return Math.abs(xy[0]) <= 180 && Math.abs(xy[1]) <= 90;
}

// Italian latitude band — projected CRS without a declared `crs`/`.prj` are
// almost always Italian regional data (EU-wide datasets ship WGS84 or declare
// their CRS, which takes the explicit path above).
const IT_LAT_MIN = 35;
const IT_LAT_MAX = 48.5;

function fwd(epsg: string, xy: number[]): [number, number] | null {
  try {
    const [lon, lat] = proj4(DEFS[epsg], proj4.WGS84).forward([xy[0], xy[1]]);
    return [lon, lat];
  } catch {
    return null;
  }
}

/** Auto-detect the CRS of projected coordinates that carry no declared CRS, by
 *  trial-reprojecting a sample coordinate. Strategy:
 *   - Gauss-Boaga (Monte Mario) has a distinctive false-easting (~1.5M / ~2.5M).
 *   - UTM 32N/33N (and the equivalent ETRS89 25832/33) are picked by checking
 *     the recovered longitude falls in the zone's band.
 *   - Web Mercator is the last resort.
 *  Bare-easting UTM 32 vs 33 is genuinely ambiguous from one point; this favours
 *  zone 32 (covers most of N/C Italy). Shapefiles normally carry a .prj and are
 *  reprojected by shpjs upstream, so this fallback rarely fires. */
function guessCrs([x, y]: number[]): string {
  if (y > 3_900_000 && y < 5_300_000) {
    if (x > 1_400_000 && x < 1_800_000) return "EPSG:3003"; // Gauss-Boaga zone 1
    if (x > 2_300_000 && x < 2_800_000) return "EPSG:3004"; // Gauss-Boaga zone 2
  }
  const zones: [string, number, number][] = [
    ["EPSG:32632", 5.5, 12.0],
    ["EPSG:32633", 12.0, 19.5],
    ["EPSG:25832", 5.5, 12.0],
    ["EPSG:25833", 12.0, 19.5],
  ];
  for (const [epsg, lonMin, lonMax] of zones) {
    const r = fwd(epsg, [x, y]);
    if (r && r[1] >= IT_LAT_MIN && r[1] <= IT_LAT_MAX && r[0] >= lonMin && r[0] <= lonMax) return epsg;
  }
  const wm = fwd("EPSG:3857", [x, y]);
  if (wm && wm[1] >= IT_LAT_MIN && wm[1] <= IT_LAT_MAX && wm[0] >= 5.5 && wm[0] <= 19.5) return "EPSG:3857";
  return "EPSG:3857";
}

/** Return a WGS84 GeoJSON, reprojecting from the declared/guessed CRS if needed. */
export function toWgs84(geojson: AnyGeo): AnyGeo {
  if (!geojson || typeof geojson !== "object") return geojson;

  const crsName = ((geojson.crs as AnyGeo)?.properties as AnyGeo)?.name;
  let epsg = epsgFromCrsName(crsName);

  // WGS84 already declared → nothing to do.
  if (epsg && (WGS84.includes(epsg) || epsg === "EPSG:4326")) return geojson;

  const sample = sampleCoord(geojson);
  if (!sample) return geojson; // empty geometry

  // No declared CRS: if coordinates already look like lon/lat, trust them;
  // otherwise auto-detect the projection from the sample coordinate.
  if (!epsg) {
    if (isLonLat(sample)) return geojson;
    epsg = guessCrs(sample);
  }

  const def = DEFS[epsg];
  if (!def) return geojson; // unknown CRS → leave as-is (better than crashing)

  let project: (xy: number[]) => number[];
  try {
    const t = proj4(def, proj4.WGS84);
    project = (xy) => {
      const [lon, lat] = t.forward([xy[0], xy[1]]);
      return xy.length > 2 ? [lon, lat, xy[2]] : [lon, lat];
    };
  } catch {
    return geojson;
  }

  const mapGeom = (g: AnyGeo): AnyGeo => {
    if (!g) return g;
    if (g.type === "GeometryCollection" && Array.isArray(g.geometries)) {
      return { ...g, geometries: (g.geometries as AnyGeo[]).map(mapGeom) };
    }
    if (g.coordinates) return { ...g, coordinates: transformCoords(g.coordinates, project) };
    return g;
  };

  if (geojson.type === "FeatureCollection" && Array.isArray(geojson.features)) {
    return {
      ...geojson,
      crs: undefined,
      features: (geojson.features as AnyGeo[]).map((f) => ({
        ...f,
        geometry: mapGeom(f.geometry as AnyGeo),
      })),
    };
  }
  if (geojson.type === "Feature") {
    return { ...geojson, crs: undefined, geometry: mapGeom(geojson.geometry as AnyGeo) };
  }
  // bare geometry
  return mapGeom(geojson);
}
