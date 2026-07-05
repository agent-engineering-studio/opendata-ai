/* Risoluzione di una FONTE chiara per il cittadino (display-only).
 *
 * Mai un link a file/API in profondità (CSV, /api/, query): sempre una
 * pagina-fonte riconoscibile col suo NOME. OSM/Overpass sono NASCOSTE (ritorna
 * null): la mappa mostra già il dettaglio, il link OSM non aggiunge nulla.
 *
 * Allineato 1:1 al backend `opendata_backend/orchestrator/sources.py`. Usato
 * dalla UI (CitationLink). */

const PORTALS: { suffix: string; url: string; name: string }[] = [
  { suffix: "isprambiente.it", url: "https://idrogeo.isprambiente.it/", name: "ISPRA IdroGEO" },
  { suffix: "istat.it", url: "https://www.istat.it/", name: "ISTAT" },
  { suffix: "dati.gov.it", url: "https://www.dati.gov.it/", name: "dati.gov.it" },
  { suffix: "ec.europa.eu", url: "https://ec.europa.eu/eurostat", name: "Eurostat" },
  { suffix: "oecd.org", url: "https://data.oecd.org/", name: "OCSE" },
];
// OSM/Overpass: dato di mappa, non una citazione → nascoste.
const HIDDEN_HOSTS = ["openstreetmap.org", "overpass-api.de", "openstreetmap.de"];
const FILE_RE = /\.(csv|json|xml|pbf|zip|xlsx?|geojson|tsv)(\?|#|$)/i;

/** Fonte chiara {href, name} per i cittadini, oppure null se va NASCOSTA
 *  (URL vuoto/non-http, OSM/Overpass). */
export function resolveSource(raw: string | undefined | null): { href: string; name: string } | null {
  if (!raw) return null;
  let u: URL;
  try {
    u = new URL(String(raw).replace(/&amp;/g, "&"));
  } catch {
    return null;
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") return null;
  const host = u.hostname.replace(/^www\./, "");

  if (HIDDEN_HOSTS.some((h) => host === h || host.endsWith("." + h))) return null;

  // OpenCoesione: la pagina del SINGOLO progetto è chiara e utile (mai il JSON).
  if (host === "opencoesione.gov.it" || host.endsWith(".opencoesione.gov.it")) {
    const m = u.pathname.match(/\/progetti\/([^/.]+)/i);
    if (m)
      return {
        href: `https://opencoesione.gov.it/it/progetti/${m[1].toLowerCase()}/`,
        name: "OpenCoesione — progetto",
      };
    return { href: "https://opencoesione.gov.it/", name: "OpenCoesione" };
  }

  const p = PORTALS.find((x) => host === x.suffix || host.endsWith("." + x.suffix));
  if (p) return { href: p.url, name: p.name };

  // Fonte sconosciuta: file/API/query → niente profondità, l'origine del sito.
  if (FILE_RE.test(u.pathname) || u.pathname.includes("/api/") || u.search) {
    return { href: u.origin + "/", name: host };
  }
  return { href: u.href, name: host };
}
