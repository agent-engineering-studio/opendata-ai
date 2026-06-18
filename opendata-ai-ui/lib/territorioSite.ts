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
const HTMLTOIMAGE_JS = "https://cdn.jsdelivr.net/npm/html-to-image@1.11.13/dist/html-to-image.js";

// Runtime di condivisione delle card: immagine (Web Share API o download), link,
// social (X/Facebook/LinkedIn/WhatsApp), embed <iframe> e modalità ?embed=ID che
// isola la singola card per l'incorporamento.
const SHARE_JS = `
(function(){
  function toast(m){var t=document.createElement('div');t.className='toast';t.textContent=m;document.body.appendChild(t);requestAnimationFrame(function(){t.classList.add('show');});setTimeout(function(){t.classList.remove('show');setTimeout(function(){t.remove();},250);},1800);}
  function baseUrl(){return location.href.split('#')[0].split('?')[0];}
  function pageUrl(id){return baseUrl()+'#'+id;}
  function embedCode(id){return '<iframe src="'+baseUrl()+'?embed='+id+'#'+id+'" width="100%" height="640" style="border:1px solid #e3e4e6;border-radius:12px" loading="lazy"></iframe>';}
  async function copy(text,msg){try{await navigator.clipboard.writeText(text);toast(msg);}catch(e){window.prompt('Copia il testo:',text);}}
  async function shareImage(el,title){
    if(typeof htmlToImage==='undefined'){toast('Immagine non disponibile (offline)');return;}
    try{
      var dataUrl=await htmlToImage.toPng(el,{backgroundColor:'#ffffff',pixelRatio:2,filter:function(n){return !(n.classList&&n.classList.contains('share'));}});
      var blob=await (await fetch(dataUrl)).blob();
      var file=new File([blob],'opendata-ai.png',{type:'image/png'});
      if(navigator.canShare&&navigator.canShare({files:[file]})){await navigator.share({files:[file],title:title});}
      else{var a=document.createElement('a');a.href=dataUrl;a.download='opendata-ai.png';a.click();toast('Immagine scaricata');}
    }catch(e){toast('Impossibile generare l\\'immagine');}
  }
  document.addEventListener('click',function(ev){
    var btn=ev.target.closest&&ev.target.closest('[data-act]');if(!btn)return;
    var bar=btn.closest('[data-share]');if(!bar)return;
    var id=bar.getAttribute('data-share');var title=bar.getAttribute('data-title')||document.title;
    var el=document.getElementById(id);var url=pageUrl(id);var act=btn.getAttribute('data-act');var text=title+' — '+url;
    if(act==='img'){shareImage(el,title);}
    else if(act==='link'){if(navigator.share){navigator.share({title:title,url:url}).catch(function(){});}else{copy(url,'Link copiato negli appunti');}}
    else if(act==='embed'){copy(embedCode(id),'Codice embed copiato negli appunti');}
    else if(act==='x'){window.open('https://twitter.com/intent/tweet?text='+encodeURIComponent(title)+'&url='+encodeURIComponent(url),'_blank','noopener');}
    else if(act==='fb'){window.open('https://www.facebook.com/sharer/sharer.php?u='+encodeURIComponent(url),'_blank','noopener');}
    else if(act==='li'){window.open('https://www.linkedin.com/sharing/share-offsite/?url='+encodeURIComponent(url),'_blank','noopener');}
    else if(act==='wa'){window.open('https://wa.me/?text='+encodeURIComponent(text),'_blank','noopener');}
  });
  try{
    var emb=new URLSearchParams(location.search).get('embed');
    if(emb){
      document.body.classList.add('embed');
      var target=document.getElementById(emb);
      if(target){
        var sec=target.closest('section');
        document.querySelectorAll('section').forEach(function(s){if(s!==sec)s.classList.add('hidden');});
        if(target.classList.contains('proposal')&&sec){sec.querySelectorAll('.proposal').forEach(function(a){if(a!==target)a.classList.add('hidden');});}
      }
    }
  }catch(e){}
})();
`;

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

/** Barra "Condividi" per una card: immagine, link/social, copia link, embed iframe. */
function shareBar(id: string, title: string): string {
  const t = esc(title);
  return `<div class="share" data-share="${id}" data-title="${t}">
    <span class="share-lbl">Condividi:</span>
    <button type="button" data-act="img" title="Salva/condividi come immagine">🖼️ Immagine</button>
    <button type="button" data-act="x" title="Condividi su X">𝕏</button>
    <button type="button" data-act="fb" title="Condividi su Facebook">f</button>
    <button type="button" data-act="li" title="Condividi su LinkedIn">in</button>
    <button type="button" data-act="wa" title="Condividi su WhatsApp">WhatsApp</button>
    <button type="button" data-act="link" title="Copia il link / condividi">🔗 Link</button>
    <button type="button" data-act="embed" title="Copia il codice per incorporare la card">&lt;/&gt; Embed</button>
  </div>`;
}

function proposalHtml(p: Proposta, id: string): string {
  const ev = (p.evidenze ?? [])
    .map((e) => `<li><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.dettaglio || e.url)}</a> <span class="muted">(${esc(e.fonte)})</span></li>`)
    .join("");
  const fin = p.finanziamento
    ? `<p class="fin"><strong>Finanziamento:</strong> ${esc(p.finanziamento.linea)} — <a href="${esc(p.finanziamento.fonte_url)}" target="_blank" rel="noopener">fonte</a></p>`
    : "";
  const liv = p.fattibilita?.livello ? `<span class="chip">${esc(p.fattibilita.livello)}</span>` : "";
  return `<article class="proposal" id="${id}">
    <h4>${esc(p.titolo)} ${liv}</h4>
    <p>${esc(p.descrizione)}</p>${fin}
    ${ev ? `<details><summary>Evidenze (${(p.evidenze ?? []).length})</summary><ul class="ev">${ev}</ul></details>` : ""}
    ${shareBar(id, p.titolo)}
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
.sec-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.sec-head h2{margin:0}
.share{display:inline-flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:12px}
.share-lbl{font-size:12px;color:var(--mut);margin-right:2px}
.share button{border:1px solid var(--bd);background:#fff;color:var(--ink);border-radius:8px;padding:3px 9px;font-size:12px;font-weight:600;cursor:pointer;line-height:1.5}
.share button:hover{background:#eef3fb;border-color:var(--p);color:var(--p)}
.proposal .share{margin-top:12px;padding-top:10px;border-top:1px dashed var(--bd)}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:var(--p9);color:#fff;padding:10px 18px;border-radius:10px;font-size:14px;z-index:9999;opacity:0;pointer-events:none;transition:opacity .2s}
.toast.show{opacity:1}
.hidden{display:none!important}
body.embed .hero,body.embed nav.toc,body.embed footer,body.embed .note{display:none!important}
body.embed{background:#fff}
body.embed section{border:none;padding:18px 0}
body.embed .share{display:none}
@media print{.share{display:none}}
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
  const add = (id: string, label: string, inner: string, shareable = true) => {
    if (!inner) return;
    nav.push([id, label]);
    const head = `<div class="sec-head"><h2>${label}</h2>${shareable ? shareBar(id, `${label} · ${scheda.comune}`) : ""}</div>`;
    sezioni.push(`<section id="${id}"><div class="wrap">${head}${inner}</div></section>`);
  };
  // Id stabili e unici per ogni proposta/idea/spunto (servono allo share per-card).
  let pn = 0;
  const propBlock = (list: Proposta[]) => list.map((p) => proposalHtml(p, `card-${pn++}`)).join("");

  if (confine) add("mappa", "Il territorio", `<div id="map" role="img" aria-label="Mappa del territorio di ${esc(scheda.comune)}"></div>`, false);
  if (scheda.sintesi?.trim()) add("sintesi", "Quadro di sintesi", `<div class="card">${mdToHtml(scheda.sintesi)}</div>`);
  if (Object.values(scheda.swot ?? {}).some((v) => (v?.length ?? 0) > 0)) add("swot", "Analisi SWOT", swotHtml(scheda));
  if (proposte.length) add("proposte", "Proposte", propBlock(proposte));
  if (idee.length) add("idee", "Idee per il territorio", `${scheda.idee_sintesi ? `<div class="card">${mdToHtml(scheda.idee_sintesi)}</div>` : ""}${propBlock(idee)}`);
  if (marketing.length)
    add("marketing", "Marketing territoriale",
      lenti.map((l) => `<div class="lente-block"><h3>${LENTE_LABEL[l] ?? l}</h3>${propBlock(marketing.filter((p) => ((p.lente as string) || "altro") === l))}</div>`).join(""));
  add("maturita", "Maturità open data", maturitaHtml(extra.scorecard));
  add("valore", "Valore del patrimonio", valoreHtml(extra.portfolio));
  add("profilo", "Profilo e investimenti", reportHtml(extra.report));
  add("fonti", "Fonti", fontiHtml(scheda.citazioni), false);

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
<script src="${HTMLTOIMAGE_JS}" crossorigin="anonymous"></script>
<script>${SHARE_JS}</script>
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
      "Apri index.html in un browser (serve una connessione per mappa e stili via CDN).\n\n" +
      "Condivisione: ogni card ha una barra 'Condividi' (immagine, X/Facebook/LinkedIn/\n" +
      "WhatsApp, link, embed iframe). L'immagine funziona anche in locale; i link e\n" +
      "l'embed puntano all'URL della pagina, quindi per condividere su social pubblica\n" +
      "prima il sito su un host (es. GitHub Pages, Netlify) e apri quell'URL.\n\n" +
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
