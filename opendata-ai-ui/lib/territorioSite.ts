/*
 * Export "sito completo" dell'analisi di Territorio: un sito statico self-contained,
 * responsive e gradevole (CSS dedicato + Bootstrap Italia via CDN), con nav sticky,
 * hero, KPI, una MAPPA Leaflet del territorio (confine comunale) e TUTTE le sezioni
 * del lavoro — sintesi, SWOT, proposte, idee, marketing, maturità, valore, profilo —
 * più un DISCLAIMER esplicito (fini costruttivi, no strumentalizzazione politica, bene
 * comune). Generato client-side e scaricato come ZIP (la UI è output:'export').
 */
import type { ProgrammaResponse, Proposta, Resource } from "@/lib/types";
import type { Portfolio, Report, Scorecard } from "@/components/territorio/TerritorioExtra";

type Extra = { scorecard?: Scorecard; report?: Report; portfolio?: Portfolio };

const BI_CSS = "https://cdn.jsdelivr.net/npm/bootstrap-italia@2.18.1/dist/css/bootstrap-italia.min.css";
const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";

const SWOT_LABEL: Record<string, string> = {
  forze: "Forze", debolezze: "Debolezze", opportunita: "Opportunità", minacce: "Minacce",
};
const SWOT_ICON: Record<string, string> = {
  forze: "💪", debolezze: "⚠️", opportunita: "🚀", minacce: "🛡️",
};
const LENTE_LABEL: Record<string, string> = {
  turismo_cultura: "Turismo & cultura", viabilita_mobilita: "Viabilità & mobilità",
  sicurezza_vivibilita: "Sicurezza & vivibilità", attrattivita_brand: "Attrattività & brand",
  altro: "Altri spunti",
};
const LEVEL_COLOR: Record<string, string> = {
  Beginner: "#dc2626", Follower: "#d97706", "Fast-tracker": "#0066cc", "Trend-setter": "#00cf86",
};
const MARKETING_GEN = new Set(["caso_analogo", "asset_sottoutilizzato", "domanda_emergente"]);
const isMarketing = (p: Proposta) => !!p.lente || (!!p.generatore && MARKETING_GEN.has(p.generatore as string));

function esc(s: unknown): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Markdown minimale → HTML (titoli, grassetto/corsivo, link, liste, paragrafi). */
function mdToHtml(src: string): string {
  const inline = (t: string) =>
    esc(t)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const lines = src.replace(/\r/g, "").split("\n");
  const out: string[] = [];
  let list: string[] | null = null;
  let listTag: "ul" | "ol" = "ul";
  const flush = () => {
    if (list) { out.push(`<${listTag}>${list.join("")}</${listTag}>`); list = null; }
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) { flush(); const lv = Math.min(h[1].length + 1, 6); out.push(`<h${lv}>${inline(h[2])}</h${lv}>`); continue; }
    const ul = line.match(/^[-*]\s+(.*)$/);
    const ol = line.match(/^\d+\.\s+(.*)$/);
    if (ul) { if (!list || listTag !== "ul") { flush(); list = []; listTag = "ul"; } list.push(`<li>${inline(ul[1])}</li>`); continue; }
    if (ol) { if (!list || listTag !== "ol") { flush(); list = []; listTag = "ol"; } list.push(`<li>${inline(ol[1])}</li>`); continue; }
    flush();
    out.push(`<p>${inline(line)}</p>`);
  }
  flush();
  return out.join("\n");
}

function proposalHtml(p: Proposta): string {
  const ev = (p.evidenze ?? [])
    .map((e) => `<li><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.dettaglio || e.url)}</a> <span class="muted">(${esc(e.fonte)})</span></li>`)
    .join("");
  const fin = p.finanziamento
    ? `<p class="fin"><strong>Finanziamento:</strong> ${esc(p.finanziamento.linea)} — <a href="${esc(p.finanziamento.fonte_url)}" target="_blank" rel="noopener">fonte</a></p>`
    : "";
  const liv = p.fattibilita?.livello ? `<span class="chip">${esc(p.fattibilita.livello)}</span>` : "";
  return `<article class="proposal">
    <h4>${esc(p.titolo)} ${liv}</h4>
    <p>${esc(p.descrizione)}</p>${fin}
    ${ev ? `<details><summary>Evidenze (${(p.evidenze ?? []).length})</summary><ul class="ev">${ev}</ul></details>` : ""}
  </article>`;
}

function swotHtml(scheda: ProgrammaResponse): string {
  const cols = (["forze", "debolezze", "opportunita", "minacce"] as const)
    .map((k) => {
      const items = (scheda.swot?.[k] ?? []).map((v) => `<li>${esc(v.testo)}</li>`).join("");
      return `<div class="swot-cell swot-${k}">
        <h4>${SWOT_ICON[k]} ${SWOT_LABEL[k]}</h4>
        <ul>${items || "<li class='muted'>—</li>"}</ul>
      </div>`;
    })
    .join("");
  return `<div class="swot-grid">${cols}</div>`;
}

function maturitaHtml(sc?: Scorecard): string {
  if (!sc) return "<p class='muted'>Non disponibile.</p>";
  if (sc.insufficient_data && sc.guida) {
    const passi = (sc.guida.passi ?? [])
      .map((p) => `<li><strong>${esc(p.titolo)}</strong><div class="muted">${esc(p.descrizione)}</div></li>`)
      .join("");
    return `<div class="callout warn"><strong>Dato insufficiente.</strong> ${esc(sc.guida.premessa)}</div>
      <ol class="guida">${passi}</ol>`;
  }
  const d = sc.dimensions ?? { policy: 0, portal: 0, quality: 0, impact: 0 };
  const color = LEVEL_COLOR[sc.level] ?? "#0066cc";
  const bar = (label: string, v: number) =>
    `<div class="bar-row"><span>${label}</span><div class="bar"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></div><b>${Math.round(v)}</b></div>`;
  return `<p><span class="level" style="background:${color}">${esc(sc.level)} · ${Math.round(sc.overall ?? 0)}/100</span>
    ${sc.n_datasets != null ? `<span class="muted"> · ${sc.n_datasets} dataset valutati</span>` : ""}</p>
    <div class="bars">${bar("Policy", d.policy)}${bar("Portale", d.portal)}${bar("Qualità", d.quality)}${bar("Impatto", d.impact)}</div>`;
}

function kpiHtml(items: [string, string][]): string {
  return `<div class="kpis">${items.map(([v, l]) => `<div class="kpi"><div class="kpi-v">${esc(v)}</div><div class="kpi-l">${esc(l)}</div></div>`).join("")}</div>`;
}

function valoreHtml(p?: Portfolio): string {
  if (!p || !p.count) return "<p class='muted'>Nessun dataset aperto valutato: il valore si misura quando l'ente pubblica i propri open data.</p>";
  return kpiHtml([
    [String(p.count), "Dataset"],
    [p.pct_hvd != null ? Math.round(p.pct_hvd) + "%" : "—", "Alto valore (HVD)"],
    [p.pct_open_license != null ? Math.round(p.pct_open_license) + "%" : "—", "Licenza aperta"],
    [p.avg_stars != null ? p.avg_stars.toFixed(1) : "—", "Stelle medie"],
    [p.avg_reuse != null ? p.avg_reuse.toFixed(1) : "—", "Riuso medio"],
  ]);
}

function reportHtml(r?: Report): string {
  if (!r) return "<p class='muted'>Non disponibile.</p>";
  const inv = r.sezioni?.investimenti ?? {};
  const eur = inv.finanziamento_totale != null
    ? new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 }).format(inv.finanziamento_totale) + " €" : "—";
  const gap = (r.sezioni?.gap_dato ?? []).map((g) => `<li>${esc(g)}</li>`).join("");
  return `${r.narrativa ? `<div class="prose">${mdToHtml(r.narrativa)}</div>` : ""}
    ${kpiHtml([[String(inv.n_progetti ?? 0), "Progetti pubblici"], [eur, "Finanziamento totale"]])}
    ${gap ? `<h4>Gap di dato</h4><ul>${gap}</ul>` : ""}`;
}

const DISCLAIMER =
  "Questo report è prodotto a soli fini costruttivi e di analisi del patrimonio pubblico " +
  "di dati. NON costituisce materiale elettorale né alcuna forma di strumentalizzazione " +
  "politica: è realizzato unicamente per il bene comune e per stimolare le PA a valorizzare " +
  "i propri open data. Le elaborazioni si basano su fonti pubbliche citate e possono " +
  "contenere imprecisioni: verificare sempre i dati alla fonte.";

function fontiHtml(citazioni: Resource[]): string {
  const items = (citazioni ?? [])
    .map((c) => `<li><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name || c.url)}</a> <span class="muted">(${esc(c.source ?? "")})</span></li>`)
    .join("");
  return items ? `<ul class="fonti">${items}</ul>` : "<p class='muted'>—</p>";
}

const STYLE = `
:root{--p:#0066cc;--p9:#002b56;--g:#00cf86;--ink:#17324d;--mut:#5b6f82;--bd:#e3e4e6;--bg:#f7f9fc}
*{box-sizing:border-box}
body{margin:0;font-family:'Titillium Web',system-ui,sans-serif;color:var(--ink);background:var(--bg);line-height:1.6}
a{color:var(--p)}
.wrap{max-width:960px;margin:0 auto;padding:0 20px}
.hero{background:linear-gradient(135deg,var(--p9),var(--p));color:#fff;padding:48px 0 40px}
.hero .tag{text-transform:uppercase;letter-spacing:.12em;font-size:12px;opacity:.85;margin:0 0 6px}
.hero h1{font-size:2rem;margin:0 0 8px;font-weight:700}
.hero p{margin:0;opacity:.9}
nav.toc{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid var(--bd);box-shadow:0 1px 4px rgba(0,0,0,.04)}
nav.toc .wrap{display:flex;flex-wrap:wrap;gap:4px;overflow-x:auto;padding:8px 20px}
nav.toc a{padding:6px 12px;border-radius:8px;text-decoration:none;font-size:14px;white-space:nowrap;color:var(--ink)}
nav.toc a:hover{background:#eef3fb}
section{padding:32px 0;border-bottom:1px solid var(--bd)}
section h2{font-size:1.4rem;margin:0 0 16px;color:var(--p9)}
.note{background:#eef6ff;border-left:4px solid var(--p);padding:14px 16px;border-radius:8px;margin:24px 0;font-size:14px}
.card{background:#fff;border:1px solid var(--bd);border-radius:12px;padding:18px;margin:0 0 16px;box-shadow:0 1px 3px rgba(0,0,0,.03)}
.muted{color:var(--mut)}
.prose h3,.prose h4{color:var(--p9);margin:18px 0 6px}
.prose p{margin:0 0 10px}
.swot-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.swot-cell{background:#fff;border:1px solid var(--bd);border-radius:12px;padding:16px}
.swot-cell h4{margin:0 0 8px;font-size:1rem}
.swot-cell ul{margin:0;padding-left:18px;font-size:14px}
.swot-forze{border-top:3px solid var(--g)}.swot-opportunita{border-top:3px solid var(--p)}
.swot-debolezze{border-top:3px solid #d97706}.swot-minacce{border-top:3px solid #dc2626}
.proposal{background:#fff;border:1px solid var(--bd);border-radius:12px;padding:16px;margin:0 0 14px}
.proposal h4{margin:0 0 6px;font-size:1.05rem}
.chip{display:inline-block;background:#eef3fb;color:var(--p);font-size:12px;font-weight:600;padding:2px 8px;border-radius:20px;vertical-align:middle}
.proposal .fin{font-size:13px;background:#f0fbf6;border-radius:8px;padding:6px 10px}
.ev{font-size:13px;margin:8px 0 0;padding-left:18px}
details summary{cursor:pointer;color:var(--p);font-size:13px}
.kpis{display:flex;flex-wrap:wrap;gap:14px;margin:8px 0}
.kpi{flex:1;min-width:120px;background:#fff;border:1px solid var(--bd);border-radius:12px;padding:14px;text-align:center}
.kpi-v{font-size:1.6rem;font-weight:700;color:var(--p)}
.kpi-l{font-size:13px;color:var(--mut)}
.level{display:inline-block;color:#fff;font-weight:600;padding:4px 12px;border-radius:20px}
.bars{margin-top:10px}
.bar-row{display:flex;align-items:center;gap:10px;font-size:13px;margin:4px 0}
.bar-row span{width:90px}.bar-row b{width:36px;text-align:right}
.bar{flex:1;background:#e7ecf3;border-radius:6px;height:12px;overflow:hidden}
.bar i{display:block;height:12px;background:var(--p)}
.callout.warn{background:#fff8e6;border-left:4px solid #d97706;padding:12px 14px;border-radius:8px;margin:0 0 12px;font-size:14px}
.guida{font-size:14px}.guida li{margin:0 0 8px}
.fonti{font-size:13px;columns:2}
#map{height:380px;border-radius:12px;border:1px solid var(--bd);overflow:hidden}
.lente-block{margin:0 0 18px}.lente-block h3{font-size:1.05rem;color:var(--p9);margin:0 0 8px}
footer{background:var(--p9);color:#fff;padding:28px 0;font-size:13px}
footer a{color:#cfe3ff}
@media(max-width:720px){.swot-grid{grid-template-columns:1fr}.hero h1{font-size:1.5rem}.fonti{columns:1}}
`;

export function buildSiteHtml(scheda: ProgrammaResponse, extra: Extra, confine?: GeoJSON.Feature | null): string {
  const proposte = scheda.proposte.filter((p) => !p.generatore && !p.lente);
  const idee = scheda.proposte.filter((p) => !!p.generatore && !isMarketing(p));
  const marketing = scheda.proposte.filter(isMarketing);
  const lenti = Array.from(new Set(marketing.map((p) => (p.lente as string) || "altro")));
  const title = `Analisi del territorio — ${esc(scheda.comune)}`;

  const nav: [string, string][] = [];
  const sezioni: string[] = [];
  const add = (id: string, label: string, inner: string) => {
    if (!inner) return;
    nav.push([id, label]);
    sezioni.push(`<section id="${id}"><div class="wrap"><h2>${label}</h2>${inner}</div></section>`);
  };

  if (confine) add("mappa", "Il territorio", `<div id="map" role="img" aria-label="Mappa del territorio di ${esc(scheda.comune)}"></div>`);
  if (scheda.sintesi?.trim()) add("sintesi", "Quadro di sintesi", `<div class="card">${mdToHtml(scheda.sintesi)}</div>`);
  if (Object.values(scheda.swot ?? {}).some((v) => (v?.length ?? 0) > 0)) add("swot", "Analisi SWOT", swotHtml(scheda));
  if (proposte.length) add("proposte", "Proposte", proposte.map(proposalHtml).join(""));
  if (idee.length) add("idee", "Idee per il territorio", `${scheda.idee_sintesi ? `<div class="card">${mdToHtml(scheda.idee_sintesi)}</div>` : ""}${idee.map(proposalHtml).join("")}`);
  if (marketing.length)
    add("marketing", "Marketing territoriale",
      lenti.map((l) => `<div class="lente-block"><h3>${LENTE_LABEL[l] ?? l}</h3>${marketing.filter((p) => ((p.lente as string) || "altro") === l).map(proposalHtml).join("")}</div>`).join(""));
  add("maturita", "Maturità open data", maturitaHtml(extra.scorecard));
  add("valore", "Valore del patrimonio", valoreHtml(extra.portfolio));
  add("profilo", "Profilo e investimenti", reportHtml(extra.report));
  add("fonti", "Fonti", fontiHtml(scheda.citazioni));

  const mapScript = confine
    ? `<script src="${LEAFLET_JS}"></script>
<script>(function(){try{
  var gj=${JSON.stringify(confine)};
  var map=L.map('map',{scrollWheelZoom:false});
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
  var layer=L.geoJSON(gj,{style:{color:'#0066cc',weight:2,fillColor:'#0066cc',fillOpacity:.12}}).addTo(map);
  map.fitBounds(layer.getBounds(),{padding:[20,20]});
}catch(e){var m=document.getElementById('map');if(m)m.style.display='none';}})();</script>`
    : "";

  return `<!DOCTYPE html><html lang="it"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title>
<link rel="stylesheet" href="${BI_CSS}">
${confine ? `<link rel="stylesheet" href="${LEAFLET_CSS}">` : ""}
<style>${STYLE}</style>
</head><body>
<header class="hero"><div class="wrap">
  <p class="tag">OpenData AI · analisi del territorio</p>
  <h1>${title}${scheda.zona ? ` · ${esc(scheda.zona)}` : ""}</h1>
  <p>${scheda.generato_il ? `Generato il ${esc(scheda.generato_il)}` : "Analisi dal patrimonio di open data pubblici"}</p>
</div></header>
<nav class="toc"><div class="wrap">${nav.map(([id, l]) => `<a href="#${id}">${l}</a>`).join("")}</div></nav>
<main>
  <div class="wrap"><div class="note" role="note"><strong>Nota.</strong> ${esc(DISCLAIMER)}</div></div>
  ${sezioni.join("\n")}
</main>
<footer><div class="wrap">
  <p>${esc(DISCLAIMER)}</p>
  <p style="margin:8px 0 0;opacity:.8">Generato da OpenData AI${scheda.generato_il ? ` · ${esc(scheda.generato_il)}` : ""}.</p>
</div></footer>
${mapScript}
</body></html>`;
}

export async function downloadSiteZip(
  scheda: ProgrammaResponse,
  extra: Extra,
  confine?: GeoJSON.Feature | null,
): Promise<void> {
  const JSZip = (await import("jszip")).default;
  const zip = new JSZip();
  const slug = (scheda.comune || "comune").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  zip.file("index.html", buildSiteHtml(scheda, extra, confine));
  zip.file(
    "LEGGIMI.txt",
    "Sito statico dell'analisi del territorio generato da OpenData AI.\n" +
      "Apri index.html in un browser (serve una connessione per mappa e stili via CDN).\n" +
      "A soli fini costruttivi / bene comune — non materiale elettorale.\n",
  );
  const blob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sito-territorio-${slug || "comune"}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}
