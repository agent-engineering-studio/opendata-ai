/*
 * Export "sito completo" dell'analisi di Territorio: un sito statico self-contained,
 * responsive e curato (CSS dedicato + Titillium Web + Bootstrap Italia/Leaflet via CDN).
 * Hero, nav sticky, disclaimer prominente in alto, idee evidenziate, mappa Leaflet del
 * territorio, card "stato maturità" molto chiara quando i dati mancano (con buone
 * pratiche per avviare la valorizzazione), profilo/investimenti leggibili, e una barra
 * "Condividi" per ogni card (immagine/social/embed). Scaricato come ZIP.
 */
import type { ProgrammaResponse, Proposta, Resource } from "@/lib/types";
import type { Portfolio, Report, Scorecard } from "@/components/territorio/TerritorioExtra";

type Extra = { scorecard?: Scorecard; report?: Report; portfolio?: Portfolio };

const BI_CSS = "https://cdn.jsdelivr.net/npm/bootstrap-italia@2.18.1/dist/css/bootstrap-italia.min.css";
const FONT_CSS = "https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700&display=swap";
const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const HTMLTOIMAGE_JS = "https://cdn.jsdelivr.net/npm/html-to-image@1.11.13/dist/html-to-image.js";

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
  Beginner: "#dc2626", Follower: "#d97706", "Fast-tracker": "#0066cc", "Trend-setter": "#00a060",
};
const FEAS_COLOR: Record<string, string> = { alta: "#00a060", media: "#d97706", bassa: "#64748b" };
const MARKETING_GEN = new Set(["caso_analogo", "asset_sottoutilizzato", "domanda_emergente"]);
const isMarketing = (p: Proposta) => !!p.lente || (!!p.generatore && MARKETING_GEN.has(p.generatore as string));

const DISCLAIMER =
  "Questo report è prodotto a soli fini costruttivi e di analisi del patrimonio pubblico " +
  "di dati. NON costituisce materiale elettorale né alcuna forma di strumentalizzazione " +
  "politica: è realizzato unicamente per il bene comune e per stimolare le PA a valorizzare " +
  "i propri open data. Le elaborazioni si basano su fonti pubbliche citate e possono " +
  "contenere imprecisioni: verificare sempre i dati alla fonte.";

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
  const flush = () => { if (list) { out.push(`<${listTag}>${list.join("")}</${listTag}>`); list = null; } };
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

/** Barra "Condividi" per una card: immagine, social, link, embed iframe. */
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

function feasChip(p: Proposta): string {
  const l = p.fattibilita?.livello;
  // "da_verificare" non viene mostrata come etichetta (poco utile/sgradevole): vale
  // la nota generale sulla fattibilità a fondo sezione.
  if (!l || l === "da_verificare") return "";
  return `<span class="chip" style="background:${FEAS_COLOR[l] ?? "#64748b"}">Fattibilità ${esc(l)}</span>`;
}

function evidenzeHtml(p: Proposta): string {
  const items = (p.evidenze ?? [])
    .map((e) => `<li><span class="ev-d">${esc(e.dettaglio || "Fonte")}</span> <a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.fonte)} ↗</a></li>`)
    .join("");
  if (!items) return "";
  return `<details class="ev"><summary>Dati e fonti (${(p.evidenze ?? []).length})</summary><ul>${items}</ul></details>`;
}

function proposalHtml(p: Proposta, id: string, variant: "proposta" | "idea" | "marketing" = "proposta"): string {
  const fin = p.finanziamento
    ? `<p class="fin"><strong>💶 Finanziamento:</strong> ${esc(p.finanziamento.linea)} — <a href="${esc(p.finanziamento.fonte_url)}" target="_blank" rel="noopener">fonte</a></p>`
    : "";
  const tag = variant === "idea" ? `<span class="card-tag idea-tag">💡 Idea</span>`
    : variant === "marketing" ? `<span class="card-tag mkt-tag">📣 Spunto</span>` : "";
  return `<article class="card-item ${variant}" id="${id}">
    <div class="ci-head">${tag}<h4>${esc(p.titolo)}</h4>${feasChip(p)}</div>
    <p>${esc(p.descrizione)}</p>${fin}
    ${evidenzeHtml(p)}
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

function barList(items: { label: string; value: number }[], fmt: (n: number) => string): string {
  const max = Math.max(1, ...items.map((i) => i.value));
  return `<div class="barlist">${items.map((i) => `<div class="bl-row">
    <span class="bl-lbl">${esc(i.label)}</span>
    <div class="bl-track"><i style="width:${Math.round((i.value / max) * 100)}%"></i></div>
    <span class="bl-val">${esc(fmt(i.value))}</span></div>`).join("")}</div>`;
}

function kpiHtml(items: [string, string][]): string {
  return `<div class="kpis">${items.map(([v, l]) => `<div class="kpi"><div class="kpi-v">${esc(v)}</div><div class="kpi-l">${esc(l)}</div></div>`).join("")}</div>`;
}

function maturitaHtml(sc?: Scorecard): string {
  if (!sc) return "<p class='muted'>Non disponibile.</p>";
  if (sc.insufficient_data && sc.guida) {
    const passi = (sc.guida.passi ?? [])
      .map((p, i) => `<li><span class="step-n">${i + 1}</span><div><strong>${esc(p.titolo.replace(/^\d+\.\s*/, ""))}</strong><div class="muted">${esc(p.descrizione)}</div></div></li>`)
      .join("");
    return `<div class="grave">
      <div class="grave-head"><span class="grave-ico">⚠️</span>
        <div><h3>Open data assenti: un'opportunità da non perdere</h3>
        <p>${esc(sc.guida.premessa)}</p></div>
      </div>
      <div class="grave-why">
        <strong>Perché conta agire ora</strong>
        <ul>
          <li><b>Trasparenza:</b> senza dati aperti cittadini e imprese non possono leggere e verificare l'azione pubblica.</li>
          <li><b>Riuso e servizi:</b> i dati pubblicati diventano app, ricerche e servizi per il territorio.</li>
          <li><b>Fondi e obblighi:</b> i dataset ad alto valore (HVD) sono richiesti dal regolamento UE e premiati nei bandi.</li>
          <li><b>Reputazione:</b> un ente che apre i dati comunica fiducia, efficienza e modernità.</li>
        </ul>
      </div>
      <h4 class="bp-title">Buone pratiche per avviare la valorizzazione</h4>
      <ol class="steps">${passi}</ol>
      <p class="muted bp-note">${esc(sc.guida.nota ?? "")}</p>
    </div>`;
  }
  const d = sc.dimensions ?? { policy: 0, portal: 0, quality: 0, impact: 0 };
  const color = LEVEL_COLOR[sc.level] ?? "#0066cc";
  const bar = (label: string, v: number) =>
    `<div class="bl-row"><span class="bl-lbl">${label}</span><div class="bl-track"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></div><span class="bl-val">${Math.round(v)}</span></div>`;
  return `<p class="lvl-line"><span class="level" style="background:${color}">${esc(sc.level)} · ${Math.round(sc.overall ?? 0)}/100</span>
    ${sc.n_datasets != null ? `<span class="muted"> · ${sc.n_datasets} dataset valutati</span>` : ""}</p>
    <div class="barlist">${bar("Policy", d.policy)}${bar("Portale", d.portal)}${bar("Qualità", d.quality)}${bar("Impatto", d.impact)}</div>`;
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
  const eur = (n?: number) => (n != null ? new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 }).format(n) + " €" : "—");
  const temi = (inv.per_tema ?? []).slice(0, 6).map((t) => ({ label: t.tema, value: t.finanziamento }));
  const gap = (r.sezioni?.gap_dato ?? []).map((g) => `<li>${esc(g)}</li>`).join("");
  return `${r.narrativa ? `<div class="prose card">${mdToHtml(r.narrativa)}</div>` : ""}
    ${kpiHtml([[String(inv.n_progetti ?? 0), "Progetti pubblici"], [eur(inv.finanziamento_totale), "Finanziamento totale"]])}
    ${temi.length ? `<h4 class="sub">Investimenti per tema</h4>${barList(temi, eur)}` : ""}
    ${gap ? `<div class="gap"><h4 class="sub">⚠️ Gap di dato</h4><ul>${gap}</ul></div>` : ""}`;
}

function fontiHtml(citazioni: Resource[]): string {
  const items = (citazioni ?? [])
    .map((c) => `<li><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name || c.url)}</a> <span class="muted">(${esc(c.source ?? "")})</span></li>`)
    .join("");
  return items ? `<ul class="fonti">${items}</ul>` : "<p class='muted'>—</p>";
}

const STYLE = `
:root{--p:#0066cc;--p7:#004a94;--p9:#002b56;--g:#00a060;--amber:#d97706;--red:#dc2626;--ink:#1b2b3a;--mut:#5b6f82;--bd:#e3e7ee;--bg:#f4f7fb;--card:#fff}
*{box-sizing:border-box}
body{margin:0;font-family:'Titillium Web',system-ui,-apple-system,sans-serif;color:var(--ink);background:var(--bg);line-height:1.65;-webkit-font-smoothing:antialiased}
a{color:var(--p);text-underline-offset:2px}
.wrap{max-width:1000px;margin:0 auto;padding:0 22px}
.hero{position:relative;overflow:hidden;background:linear-gradient(135deg,var(--p9),var(--p));color:#fff;padding:56px 0 48px}
.hero::after{content:"";position:absolute;right:-80px;top:-80px;width:320px;height:320px;border-radius:50%;background:rgba(255,255,255,.07)}
.hero .tag{text-transform:uppercase;letter-spacing:.16em;font-size:12px;opacity:.85;margin:0 0 8px;font-weight:600}
.hero h1{font-size:2.3rem;margin:0 0 8px;font-weight:700;line-height:1.15}
.hero p{margin:0;opacity:.92}
nav.toc{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.95);backdrop-filter:saturate(150%) blur(6px);border-bottom:1px solid var(--bd)}
nav.toc .wrap{display:flex;flex-wrap:nowrap;gap:4px;overflow-x:auto;padding:10px 22px}
nav.toc a{padding:6px 14px;border-radius:999px;text-decoration:none;font-size:14px;font-weight:600;white-space:nowrap;color:var(--ink)}
nav.toc a:hover{background:#e9f1fc;color:var(--p7)}
main>.wrap:first-child{margin-top:26px}
section{padding:38px 0;border-bottom:1px solid var(--bd)}
section:last-of-type{border-bottom:none}
section h2{font-size:1.5rem;margin:0;color:var(--p9);display:flex;align-items:center;gap:10px}
section h2::before{content:"";width:6px;height:24px;border-radius:4px;background:var(--p)}
.disclaimer{display:flex;gap:14px;align-items:flex-start;background:linear-gradient(135deg,#eaf3ff,#f4f9ff);border:1px solid #cfe2fb;border-left:5px solid var(--p);padding:18px 20px;border-radius:14px;margin:0 0 8px;font-size:15.5px;line-height:1.6}
.disclaimer .di{font-size:1.6rem;line-height:1}
.disclaimer strong{color:var(--p9)}
.card{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:20px;box-shadow:0 1px 3px rgba(16,42,76,.05)}
.muted{color:var(--mut)}
.sub{font-size:1rem;color:var(--p9);margin:18px 0 8px}
.prose h3,.prose h4{color:var(--p9);margin:18px 0 6px}
.prose p{margin:0 0 10px}.prose>:first-child{margin-top:0}
.card-item{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:18px 20px;margin:0 0 16px;box-shadow:0 1px 3px rgba(16,42,76,.05);transition:box-shadow .15s,transform .15s}
.card-item:hover{box-shadow:0 6px 22px rgba(16,42,76,.10);transform:translateY(-2px)}
.ci-head{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin:0 0 6px}
.ci-head h4{margin:0;font-size:1.12rem;flex:1 1 auto}
.card-tag{font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px;color:#fff}
.idea-tag{background:linear-gradient(135deg,#f59e0b,#f97316)}
.mkt-tag{background:linear-gradient(135deg,#7c3aed,#a855f7)}
.card-item.idea{border-left:5px solid #f59e0b;background:linear-gradient(180deg,#fffdf6,#fff)}
.card-item.marketing{border-left:5px solid #a855f7}
.chip{display:inline-block;color:#fff;font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px}
.fin{font-size:14px;background:#f0fbf6;border:1px solid #cdeede;border-radius:10px;padding:8px 12px;margin:8px 0}
details.ev{margin-top:8px}details.ev summary{cursor:pointer;color:var(--p7);font-size:13px;font-weight:600}
details.ev ul{font-size:13px;margin:8px 0 0;padding-left:18px}
.ev-d{color:var(--ink)}
.note-feas{font-size:13px;color:var(--mut);font-style:italic;margin:6px 0 0}
.kpis{display:flex;flex-wrap:wrap;gap:14px;margin:12px 0}
.kpi{flex:1;min-width:130px;background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:16px;text-align:center;box-shadow:0 1px 3px rgba(16,42,76,.05)}
.kpi-v{font-size:1.7rem;font-weight:700;color:var(--p)}
.kpi-l{font-size:13px;color:var(--mut)}
.lvl-line{margin:0 0 10px}
.level{display:inline-block;color:#fff;font-weight:700;padding:5px 14px;border-radius:999px}
.barlist{margin-top:6px}
.bl-row{display:flex;align-items:center;gap:12px;font-size:13px;margin:6px 0}
.bl-lbl{width:150px;flex-shrink:0}.bl-val{width:90px;text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.bl-track{flex:1;background:#e7ecf3;border-radius:6px;height:12px;overflow:hidden}
.bl-track i{display:block;height:12px;background:linear-gradient(90deg,var(--p),#3b8ae0)}
.swot-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.swot-cell{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:18px;box-shadow:0 1px 3px rgba(16,42,76,.05)}
.swot-cell h4{margin:0 0 10px;font-size:1.05rem}
.swot-cell ul{margin:0;padding-left:18px;font-size:14px}
.swot-forze{border-top:4px solid var(--g)}.swot-opportunita{border-top:4px solid var(--p)}
.swot-debolezze{border-top:4px solid var(--amber)}.swot-minacce{border-top:4px solid var(--red)}
.grave{border:1px solid #f3cf9e;border-radius:16px;overflow:hidden;background:var(--card);box-shadow:0 2px 10px rgba(16,42,76,.06)}
.grave-head{display:flex;gap:16px;align-items:flex-start;background:linear-gradient(135deg,#fff4e3,#fde9cf);padding:20px 22px}
.grave-ico{font-size:2rem;line-height:1}
.grave-head h3{margin:0 0 4px;color:#92400e;font-size:1.25rem}
.grave-head p{margin:0;color:#7c5a26}
.grave-why{padding:18px 22px;background:#fffdf8;border-top:1px solid #f3e2c6}
.grave-why ul{margin:8px 0 0;padding-left:18px;font-size:14px}
.bp-title{margin:22px 22px 0;color:var(--p9)}
.steps{list-style:none;margin:14px 0 0;padding:0 22px 8px;display:grid;gap:12px}
.steps li{display:flex;gap:14px;align-items:flex-start;background:#fff;border:1px solid var(--bd);border-radius:12px;padding:14px 16px}
.step-n{flex-shrink:0;width:30px;height:30px;border-radius:50%;background:var(--p);color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center}
.steps .muted{font-size:13.5px}
.bp-note{padding:0 22px 18px;font-size:12px}
.gap ul{font-size:14px;margin:6px 0 0;padding-left:18px}
.fonti{font-size:13px;columns:2;column-gap:28px}
#map{height:400px;border-radius:16px;border:1px solid var(--bd);overflow:hidden;box-shadow:0 2px 10px rgba(16,42,76,.06)}
.lente-block{margin:0 0 20px}.lente-block h3{font-size:1.1rem;color:var(--p9);margin:0 0 10px}
.share{display:inline-flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:14px;padding-top:12px;border-top:1px dashed var(--bd)}
.share-lbl{font-size:12px;color:var(--mut)}
.share button{border:1px solid var(--bd);background:#fff;color:var(--ink);border-radius:8px;padding:4px 10px;font-size:12px;font-weight:600;cursor:pointer;line-height:1.5}
.share button:hover{background:#eef3fb;border-color:var(--p);color:var(--p)}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:var(--p9);color:#fff;padding:11px 20px;border-radius:12px;font-size:14px;z-index:9999;opacity:0;pointer-events:none;transition:opacity .2s}
.toast.show{opacity:1}
.hidden{display:none!important}
body.embed .hero,body.embed nav.toc,body.embed footer,body.embed .disclaimer{display:none!important}
body.embed{background:#fff}body.embed section{border:none;padding:20px 0}body.embed .share{display:none}
footer{background:var(--p9);color:#fff;padding:30px 0;font-size:13px}
footer a{color:#cfe3ff}
@media print{.share{display:none}}
@media(max-width:720px){.swot-grid{grid-template-columns:1fr}.hero h1{font-size:1.7rem}.fonti{columns:1}.bl-lbl{width:110px}}
`;

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
        if(target.classList.contains('card-item')&&sec){sec.querySelectorAll('.card-item').forEach(function(a){if(a!==target)a.classList.add('hidden');});}
      }
    }
  }catch(e){}
})();
`;

export function buildSiteHtml(scheda: ProgrammaResponse, extra: Extra, confine?: GeoJSON.Feature | null): string {
  const proposte = scheda.proposte.filter((p) => !p.generatore && !p.lente);
  const idee = scheda.proposte.filter((p) => !!p.generatore && !isMarketing(p));
  const marketing = scheda.proposte.filter(isMarketing);
  const lenti = Array.from(new Set(marketing.map((p) => (p.lente as string) || "altro")));
  const title = `Analisi del territorio — ${esc(scheda.comune)}`;
  const feasNote = `<p class="note-feas">La fattibilità indicata è una stima preliminare e va verificata con l'ente prima di qualsiasi decisione.</p>`;

  const nav: [string, string][] = [];
  const sezioni: string[] = [];
  const add = (id: string, label: string, inner: string, shareable = true) => {
    if (!inner) return;
    nav.push([id, label]);
    const head = `<div class="sec-head"><h2>${label}</h2>${shareable ? shareBar(id, `${label} · ${scheda.comune}`) : ""}</div>`;
    sezioni.push(`<section id="${id}"><div class="wrap">${head}${inner}</div></section>`);
  };
  let pn = 0;
  const propBlock = (list: Proposta[], variant: "proposta" | "idea" | "marketing") =>
    list.map((p) => proposalHtml(p, `card-${pn++}`, variant)).join("");

  if (confine) add("mappa", "Il territorio", `<div id="map" role="img" aria-label="Mappa del territorio di ${esc(scheda.comune)}"></div>`, false);
  if (scheda.sintesi?.trim()) add("sintesi", "Quadro di sintesi", `<div class="card prose">${mdToHtml(scheda.sintesi)}</div>`);
  if (Object.values(scheda.swot ?? {}).some((v) => (v?.length ?? 0) > 0)) add("swot", "Analisi SWOT", swotHtml(scheda));
  if (proposte.length) add("proposte", "Proposte", propBlock(proposte, "proposta") + feasNote);
  if (idee.length) add("idee", "Idee per il territorio", `${scheda.idee_sintesi ? `<div class="card prose">${mdToHtml(scheda.idee_sintesi)}</div>` : ""}${propBlock(idee, "idea")}${feasNote}`);
  if (marketing.length)
    add("marketing", "Marketing territoriale",
      lenti.map((l) => `<div class="lente-block"><h3>${LENTE_LABEL[l] ?? l}</h3>${propBlock(marketing.filter((p) => ((p.lente as string) || "altro") === l), "marketing")}</div>`).join(""));
  add("maturita", "Stato della maturità open data", maturitaHtml(extra.scorecard));
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
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="${FONT_CSS}">
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
  <div class="wrap"><div class="disclaimer" role="note"><span class="di" aria-hidden="true">ℹ️</span><div><strong>A soli fini costruttivi.</strong> ${esc(DISCLAIMER)}</div></div></div>
  ${sezioni.join("\n")}
</main>
<footer><div class="wrap">
  <p style="opacity:.85">${esc(DISCLAIMER)}</p>
  <p style="margin:8px 0 0;opacity:.7">Generato da OpenData AI${scheda.generato_il ? ` · ${esc(scheda.generato_il)}` : ""}.</p>
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
      "Apri index.html in un browser (serve una connessione per mappa, font e stili via CDN).\n\n" +
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
