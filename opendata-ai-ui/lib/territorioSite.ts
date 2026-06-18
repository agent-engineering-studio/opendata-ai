/*
 * Export "sito completo" dell'analisi di Territorio (F3): un sito statico
 * self-contained (design Bootstrap Italia via CDN) con TUTTE le sezioni del lavoro
 * — sintesi, SWOT, proposte, idee, marketing, maturità/guida, valore, profilo —
 * più un DISCLAIMER esplicito (fini costruttivi, no strumentalizzazione politica,
 * bene comune). Generato client-side e scaricato come ZIP (la UI è output:'export').
 */
import type { ProgrammaResponse, Proposta, Resource } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Extra = { scorecard?: any; report?: any; portfolio?: any };

const BI_CSS = "https://cdn.jsdelivr.net/npm/bootstrap-italia@2.18.1/dist/css/bootstrap-italia.min.css";

const SWOT_LABEL: Record<string, string> = {
  forze: "Forze", debolezze: "Debolezze", opportunita: "Opportunità", minacce: "Minacce",
};
const LENTE_LABEL: Record<string, string> = {
  turismo_cultura: "Turismo & cultura", viabilita_mobilita: "Viabilità & mobilità",
  sicurezza_vivibilita: "Sicurezza & vivibilità", attrattivita_brand: "Attrattività & brand",
  altro: "Altri spunti",
};
const MARKETING_GEN = new Set(["caso_analogo", "asset_sottoutilizzato", "domanda_emergente"]);

function esc(s: unknown): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
const isMarketing = (p: Proposta) => !!p.lente || (!!p.generatore && MARKETING_GEN.has(p.generatore as string));

function proposalHtml(p: Proposta): string {
  const ev = (p.evidenze ?? [])
    .map((e) => `<li><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.dettaglio || e.url)}</a> <span class="text-muted">(${esc(e.fonte)})</span></li>`)
    .join("");
  const fin = p.finanziamento
    ? `<p class="small"><strong>Finanziamento:</strong> ${esc(p.finanziamento.linea)} — <a href="${esc(p.finanziamento.fonte_url)}" target="_blank" rel="noopener">fonte</a></p>`
    : "";
  return `<div class="card mb-3"><div class="card-body">
    <h4 class="h6">${esc(p.titolo)} <span class="badge bg-primary">${esc(p.fattibilita?.livello ?? "")}</span></h4>
    <p>${esc(p.descrizione)}</p>${fin}
    ${ev ? `<ul class="small">${ev}</ul>` : ""}
  </div></div>`;
}

function swotHtml(scheda: ProgrammaResponse): string {
  const cols = (["forze", "debolezze", "opportunita", "minacce"] as const)
    .map((k) => {
      const items = (scheda.swot?.[k] ?? []).map((v) => `<li>${esc(v.testo)}</li>`).join("");
      return `<div class="col-md-6 mb-3"><div class="card h-100"><div class="card-body">
        <h4 class="h6">${SWOT_LABEL[k]}</h4><ul class="small mb-0">${items || "<li class='text-muted'>—</li>"}</ul>
      </div></div></div>`;
    })
    .join("");
  return `<div class="row">${cols}</div>`;
}

function maturitaHtml(sc: any): string {
  if (!sc) return "<p class='text-muted'>Non disponibile.</p>";
  if (sc.insufficient_data && sc.guida) {
    const passi = (sc.guida.passi ?? [])
      .map((p: any) => `<li><strong>${esc(p.titolo)}</strong><div class="small">${esc(p.descrizione)}</div></li>`)
      .join("");
    return `<div class="alert alert-warning"><strong>Dato insufficiente.</strong> ${esc(sc.guida.premessa)}</div>
      <ol>${passi}</ol>
      <p class="small text-muted">${esc(sc.guida.nota ?? "")}</p>`;
  }
  const d = sc.dimensions ?? {};
  return `<p><span class="badge bg-success">${esc(sc.level)} · ${Math.round(sc.overall ?? 0)}/100</span></p>
    <p class="small text-muted">Policy ${Math.round(d.policy ?? 0)} · Portale ${Math.round(d.portal ?? 0)} ·
    Qualità ${Math.round(d.quality ?? 0)} · Impatto ${Math.round(d.impact ?? 0)}${sc.n_datasets != null ? ` · ${sc.n_datasets} dataset` : ""}</p>`;
}

function valoreHtml(p: any): string {
  if (!p || !p.count) return "<p class='text-muted'>Nessun dataset valutato per questo comune.</p>";
  const kpi = (label: string, v: string) => `<div class="col text-center"><div class="h5 text-primary mb-0">${v}</div><div class="small text-muted">${label}</div></div>`;
  return `<div class="row">${kpi("Dataset", String(p.count))}${kpi("HVD", p.pct_hvd != null ? Math.round(p.pct_hvd) + "%" : "—")}${kpi("Licenza aperta", p.pct_open_license != null ? Math.round(p.pct_open_license) + "%" : "—")}${kpi("Stelle", p.avg_stars != null ? p.avg_stars.toFixed(1) : "—")}</div>`;
}

function reportHtml(r: any): string {
  if (!r) return "<p class='text-muted'>Non disponibile.</p>";
  const inv = r.sezioni?.investimenti ?? {};
  const eur = inv.finanziamento_totale != null
    ? new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 }).format(inv.finanziamento_totale) + " €" : "—";
  const gap = (r.sezioni?.gap_dato ?? []).map((g: string) => esc(g)).join(" · ");
  return `${r.narrativa ? `<p>${esc(r.narrativa)}</p>` : ""}
    <p class="small"><strong>Investimenti pubblici:</strong> ${inv.n_progetti ?? 0} progetti · ${eur} finanziati</p>
    ${gap ? `<p class="small text-muted"><strong>Gap di dato:</strong> ${gap}</p>` : ""}`;
}

function fontiHtml(citazioni: Resource[]): string {
  const items = (citazioni ?? [])
    .map((c) => `<li><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name || c.url)}</a> <span class="text-muted">(${esc(c.source ?? "")})</span></li>`)
    .join("");
  return items ? `<ul class="small">${items}</ul>` : "<p class='text-muted'>—</p>";
}

const DISCLAIMER =
  "Questo report è prodotto a soli fini costruttivi e di analisi del patrimonio pubblico " +
  "di dati. NON costituisce materiale elettorale né alcuna forma di strumentalizzazione " +
  "politica: è realizzato unicamente per il bene comune e per stimolare le PA a valorizzare " +
  "i propri open data. Le elaborazioni si basano su fonti pubbliche citate e possono " +
  "contenere imprecisioni: verificare sempre i dati alla fonte.";

export function buildSiteHtml(scheda: ProgrammaResponse, extra: Extra): string {
  const proposte = scheda.proposte.filter((p) => !p.generatore && !p.lente);
  const idee = scheda.proposte.filter((p) => !!p.generatore && !isMarketing(p));
  const marketing = scheda.proposte.filter(isMarketing);
  const lenti = Array.from(new Set(marketing.map((p) => (p.lente as string) || "altro")));
  const sezione = (titolo: string, inner: string) =>
    `<section class="mb-5"><h2 class="h4 border-bottom pb-2">${titolo}</h2>${inner}</section>`;

  const title = `Analisi del territorio — ${esc(scheda.comune)}`;
  return `<!DOCTYPE html><html lang="it"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title>
<link rel="stylesheet" href="${BI_CSS}">
<style>body{padding:0} .container{max-width:980px} section ul{padding-left:1.1rem}</style>
</head><body>
<header class="bg-primary text-white py-4"><div class="container">
  <p class="small text-uppercase mb-1" style="opacity:.8;letter-spacing:.1em">OpenData AI · analisi del territorio</p>
  <h1 class="h2 mb-0">${title}</h1>
</div></header>
<main class="container py-4">
  <div class="alert alert-info" role="note"><strong>Nota.</strong> ${esc(DISCLAIMER)}</div>
  ${scheda.sintesi ? sezione("Quadro di sintesi", `<p>${esc(scheda.sintesi)}</p>`) : ""}
  ${sezione("Analisi SWOT", swotHtml(scheda))}
  ${proposte.length ? sezione("Proposte", proposte.map(proposalHtml).join("")) : ""}
  ${idee.length ? sezione("Idee per il territorio", `${scheda.idee_sintesi ? `<p>${esc(scheda.idee_sintesi)}</p>` : ""}${idee.map(proposalHtml).join("")}`) : ""}
  ${marketing.length ? sezione("Marketing territoriale", lenti.map((l) => `<h3 class="h6 mt-3">${LENTE_LABEL[l] ?? l}</h3>${marketing.filter((p) => ((p.lente as string) || "altro") === l).map(proposalHtml).join("")}`).join("")) : ""}
  ${sezione("Maturità open data", maturitaHtml(extra.scorecard))}
  ${sezione("Valore del patrimonio dati", valoreHtml(extra.portfolio))}
  ${sezione("Profilo e investimenti", reportHtml(extra.report))}
  ${sezione("Fonti", fontiHtml(scheda.citazioni))}
</main>
<footer class="bg-light py-4 mt-4"><div class="container small text-muted">
  <p class="mb-1">${esc(DISCLAIMER)}</p>
  <p class="mb-0">Generato da OpenData AI${scheda.generato_il ? ` · ${esc(scheda.generato_il)}` : ""}.</p>
</div></footer>
</body></html>`;
}

export async function downloadSiteZip(scheda: ProgrammaResponse, extra: Extra): Promise<void> {
  const JSZip = (await import("jszip")).default;
  const zip = new JSZip();
  const slug = (scheda.comune || "comune").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  zip.file("index.html", buildSiteHtml(scheda, extra));
  zip.file(
    "LEGGIMI.txt",
    "Sito statico dell'analisi del territorio generato da OpenData AI.\n" +
      "Apri index.html in un browser. A soli fini costruttivi / bene comune — non materiale elettorale.\n",
  );
  const blob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sito-territorio-${slug || "comune"}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}
