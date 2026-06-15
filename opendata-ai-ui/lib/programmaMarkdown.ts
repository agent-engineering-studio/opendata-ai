/*
 * Export Markdown della scheda /territorio.
 *
 * L'"Esporta PDF" via window.print() ritagliava il report a una pagina; il
 * Markdown è completo, leggibile ovunque e versionabile. Serializza la stessa
 * ProgrammaResponse renderizzata in pagina (sintesi + SWOT + proposte + idee +
 * fonti), mantenendo le etichette UTENTE (generatori, fattibilità, quadranti).
 */
import type {
  Evidenza,
  Finanziamento,
  LivelloFattibilita,
  ProgrammaResponse,
  Proposta,
} from "@/lib/types";

const SWOT_LABEL: Record<string, string> = {
  forze: "Forze",
  debolezze: "Debolezze",
  opportunita: "Opportunità",
  minacce: "Minacce",
};

const GENERATORE_LABEL: Record<string, string> = {
  gap_comparativo: "Fatto altrove",
  fabbisogno: "Bisogno scoperto",
  incompiuto: "Da completare",
  finestra_finanziamento: "Finanziabile ora",
  caso_analogo: "Caso analogo",
  asset_sottoutilizzato: "Asset da valorizzare",
  domanda_emergente: "Domanda emergente",
};

const LENTE_LABEL: Record<string, string> = {
  turismo_cultura: "Turismo & cultura",
  viabilita_mobilita: "Viabilità & mobilità",
  sicurezza_vivibilita: "Sicurezza & vivibilità",
  attrattivita_brand: "Attrattività & brand",
  altro: "Altri spunti",
};

const MARKETING_GENERATORI = new Set([
  "caso_analogo",
  "asset_sottoutilizzato",
  "domanda_emergente",
]);

function isMarketing(p: Proposta): boolean {
  return (!!p.generatore && MARKETING_GENERATORI.has(p.generatore)) || !!p.lente;
}

const DISCLAIMER_ADDENDUM =
  " I dati aperti possono risultare disallineati rispetto allo stato reale " +
  "dell'amministrazione per tempi burocratici; l'ingestione dei documenti nella " +
  "knowledge base aggiorna la conoscenza e sollecita l'allineamento delle fonti.";

const FATTIBILITA_LABEL: Record<LivelloFattibilita, string> = {
  alta: "Fattibilità alta",
  media: "Fattibilità media",
  bassa: "Fattibilità bassa",
  da_verificare: "Da verificare",
};

function ratioPct(ratio: number | null | undefined): string | null {
  if (ratio === null || ratio === undefined) return null;
  return `${Math.round(ratio * 100)}%`;
}

function evidenzaLine(e: Evidenza): string {
  const tier = e.tier === "documentale" ? " _(documentale)_" : "";
  const ext = e.fonte_tipo === "ispirazione_esterna" ? " _(ispirazione esterna)_" : "";
  const dettaglio = e.dettaglio?.trim() ? `${e.dettaglio.trim()} ` : "";
  return `- **${e.fonte}**${tier}${ext}: ${dettaglio}([fonte](${e.url}))`;
}

function finanziamentoLine(f: Finanziamento): string {
  const stato = f.stato?.trim() ? ` — ${f.stato.trim()}` : "";
  return `**Finanziamento:** ${f.linea} ([linea](${f.fonte_url}))${stato}`;
}

function propostaBlock(p: Proposta): string {
  const lines: string[] = [];
  const gen = p.generatore ? GENERATORE_LABEL[p.generatore] ?? p.generatore : null;
  const lente = p.lente ? LENTE_LABEL[p.lente] ?? p.lente : null;
  const tag = [lente, gen].filter(Boolean).join(" · ");
  lines.push(`### ${p.titolo}${tag ? ` _(${tag})_` : ""}`);

  const liv = FATTIBILITA_LABEL[p.fattibilita.livello] ?? p.fattibilita.livello;
  const ratio = ratioPct(p.fattibilita.spend_ratio_storico);
  lines.push(`*${liv}${ratio ? ` · capacità di spesa storica ${ratio}` : ""}*`);

  if (p.descrizione?.trim()) lines.push("", p.descrizione.trim());
  if (p.fattibilita.motivazione?.trim()) {
    lines.push("", `**Perché questo livello:** ${p.fattibilita.motivazione.trim()}`);
  }
  if (p.finanziamento) lines.push("", finanziamentoLine(p.finanziamento));
  if (p.evidenze.length) {
    lines.push("", "**Evidenze:**", ...p.evidenze.map(evidenzaLine));
  }
  return lines.join("\n");
}

/** Serializza la scheda in Markdown (stesso contenuto della pagina). */
export function schedaToMarkdown(s: ProgrammaResponse): string {
  const marketing = s.proposte.filter(isMarketing);
  const idee = s.proposte.filter((p) => p.generatore && !isMarketing(p));
  const proposte = s.proposte.filter((p) => !p.generatore && !p.lente);
  const out: string[] = [];

  const titolo = `Analisi del territorio — comune ${s.comune}${s.zona ? ` · ${s.zona}` : ""}`;
  out.push(`# ${titolo}`, "");
  out.push(`*Generata il ${new Date(s.generato_il).toLocaleString("it-IT")}*`, "");
  out.push(`> ${(s.disclaimer?.trim() || "") + DISCLAIMER_ADDENDUM}`.trim(), "");

  if (s.sintesi?.trim()) {
    out.push("## Quadro di sintesi", "", s.sintesi.trim(), "");
  }

  const swotKeys = Object.keys(SWOT_LABEL).filter((k) => (s.swot[k]?.length ?? 0) > 0);
  if (swotKeys.length) {
    out.push("## Analisi SWOT", "");
    for (const key of swotKeys) {
      out.push(`### ${SWOT_LABEL[key]}`, "");
      for (const voce of s.swot[key]) {
        out.push(`- ${voce.testo.trim()}`);
        for (const e of voce.evidenze) out.push(`  ${evidenzaLine(e)}`);
      }
      out.push("");
    }
  }

  // Analisi UNICA: Proposte, Idee e Marketing sono sezioni dello stesso report.
  out.push("## Proposte", "");
  if (proposte.length === 0) {
    out.push("_Nessuna proposta ha superato la verifica delle fonti._", "");
  } else {
    for (const p of proposte) out.push(propostaBlock(p), "");
  }

  if (idee.length > 0) {
    out.push("## Idee per il territorio", "");
    if (s.idee_sintesi?.trim()) out.push(s.idee_sintesi.trim(), "");
    out.push(
      "_Spunti generati dagli scarti tra dati e attuato: confronti con comuni " +
        "simili, bisogni scoperti, progetti fermi, risorse disponibili. " +
        "Elencate dalla più promettente._",
      "",
    );
    for (const p of idee) out.push(propostaBlock(p), "");
  }

  if (marketing.length > 0) {
    out.push("## Marketing territoriale — spunti di attrattività", "");
    out.push(
      "_Spunti di posizionamento ispirati a iniziative di altri enti: ogni spunto " +
        "cita una premessa locale e un precedente esterno. Non sono atti " +
        "amministrativi né progetti finanziati._",
      "",
    );
    const lenti = Array.from(new Set(marketing.map((p) => (p.lente as string) || "altro")));
    for (const lente of lenti) {
      out.push(`### ${LENTE_LABEL[lente] ?? lente}`, "");
      for (const p of marketing.filter((p) => ((p.lente as string) || "altro") === lente)) {
        out.push(propostaBlock(p), "");
      }
    }
  }

  if (s.citazioni.length) {
    out.push("## Fonti", "");
    for (const c of s.citazioni) {
      const fmt = c.format ? ` (${c.format})` : "";
      out.push(`- [${c.name || c.url}](${c.url})${fmt}`);
    }
    out.push("");
  }

  return out.join("\n");
}

/** Innesca il download del Markdown come file `.md`. */
export function downloadSchedaMarkdown(s: ProgrammaResponse): void {
  const md = schedaToMarkdown(s);
  const slug = `${s.comune}${s.zona ? `-${s.zona}` : ""}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `analisi-territorio-${slug || "report"}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
