/*
 * Export PDF della scheda /territorio — ben formattato, con logo e TUTTE le
 * proposte/idee.
 *
 * `window.print()` ritagliava il report a una pagina; qui costruiamo un PDF
 * vettoriale (testo selezionabile, paginazione automatica) dagli stessi dati
 * strutturati di `ProgrammaResponse`, con header/footer di brand "OpenData AI".
 *
 * pdfmake è caricato con import dinamico: gira solo client-side (la UI è
 * `output: 'export'`, niente runtime server) e solo al click, fuori dal bundle
 * iniziale.
 */
import type { Content, TDocumentDefinitions } from "pdfmake/interfaces";
import type {
  Evidenza,
  Finanziamento,
  LivelloFattibilita,
  ProgrammaResponse,
  Proposta,
} from "@/lib/types";

const BRAND = {
  primary: "#0066cc",
  primary900: "#002b56",
  text: "#17324d",
  muted: "#5b6f82",
  green: "#00cf86",
  border: "#e3e4e6",
  bgMuted: "#f5f5f5",
};

// Mark del logo (solidi, niente gradienti → resa pdfmake/SVG affidabile).
const LOGO_MARK = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect width="48" height="48" rx="11" fill="#0066cc"/><path d="M24 9c-7.18 0-13 5.6-13 12.5C11 31 24 40 24 40s13-9 13-18.5C37 14.6 31.18 9 24 9z" fill="#ffffff"/><circle cx="24" cy="21.5" r="5" fill="#00cf86"/></svg>`;

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
};

const FATTIBILITA: Record<LivelloFattibilita, { label: string; color: string }> = {
  alta: { label: "Fattibilità alta", color: "#008055" },
  media: { label: "Fattibilità media", color: "#a66300" },
  bassa: { label: "Fattibilità bassa", color: "#d9364f" },
  da_verificare: { label: "Da verificare", color: BRAND.muted },
};

function ratioPct(ratio: number | null | undefined): string | null {
  if (ratio === null || ratio === undefined) return null;
  return `${Math.round(ratio * 100)}%`;
}

/** Riga evidenza: dettaglio + link "(fonte)" cliccabile e verificabile. */
function evidenzaInline(e: Evidenza): Content {
  const tier = e.tier === "documentale" ? " [documentale]" : "";
  return {
    text: [
      { text: `${e.fonte}${tier}: `, bold: true, color: BRAND.primary900 },
      { text: e.dettaglio?.trim() ? `${e.dettaglio.trim()} ` : "" },
      { text: "(fonte)", link: e.url, color: BRAND.primary, decoration: "underline" },
    ],
    fontSize: 8,
    color: BRAND.muted,
    margin: [10, 1, 0, 1],
  };
}

function finanziamentoInline(f: Finanziamento): Content {
  const stato = f.stato?.trim() ? ` — ${f.stato.trim()}` : "";
  return {
    text: [
      { text: "Finanziamento: ", bold: true },
      { text: f.linea },
      { text: " (linea)", link: f.fonte_url, color: BRAND.primary, decoration: "underline" },
      { text: stato },
    ],
    fontSize: 9,
    margin: [0, 3, 0, 0],
  };
}

/** Una proposta o idea come "card" riquadrata. */
function propostaCard(p: Proposta): Content {
  const gen = p.generatore ? GENERATORE_LABEL[p.generatore] ?? p.generatore : null;
  const fatt = FATTIBILITA[p.fattibilita.livello] ?? FATTIBILITA.da_verificare;
  const ratio = ratioPct(p.fattibilita.spend_ratio_storico);

  const inner: Content[] = [
    { text: p.titolo, bold: true, fontSize: 11, color: BRAND.primary900 },
    {
      columns: [
        { text: fatt.label, color: "#ffffff", background: fatt.color, fontSize: 8, bold: true, width: "auto", margin: [0, 2, 0, 2] },
        ...(gen
          ? [{ text: gen, color: BRAND.primary, fontSize: 8, bold: true, margin: [8, 3, 0, 0], width: "auto" } as Content]
          : []),
        ...(ratio
          ? [{ text: `capacità di spesa storica ${ratio}`, color: BRAND.muted, fontSize: 8, margin: [8, 3, 0, 0] } as Content]
          : []),
      ],
      columnGap: 0,
      margin: [0, 2, 0, 4],
    },
  ];
  if (p.descrizione?.trim()) inner.push({ text: p.descrizione.trim(), fontSize: 9.5, margin: [0, 0, 0, 3], alignment: "justify" });
  if (p.fattibilita.motivazione?.trim()) {
    inner.push({
      text: [{ text: "Perché questo livello: ", bold: true }, { text: p.fattibilita.motivazione.trim() }],
      fontSize: 9,
      color: BRAND.muted,
      margin: [0, 0, 0, 2],
    });
  }
  if (p.finanziamento) inner.push(finanziamentoInline(p.finanziamento));
  if (p.evidenze.length) {
    inner.push({ text: "Premesse verificabili:", bold: true, fontSize: 8.5, margin: [0, 4, 0, 1] });
    inner.push(...p.evidenze.map(evidenzaInline));
  }

  return {
    table: { widths: ["*"], body: [[{ stack: inner, margin: [8, 6, 8, 6] }]] },
    layout: {
      hLineWidth: () => 0.75,
      vLineWidth: () => 0.75,
      hLineColor: () => BRAND.border,
      vLineColor: () => BRAND.border,
    },
    margin: [0, 0, 0, 8],
  };
}

function sectionTitle(text: string): Content {
  return {
    text,
    fontSize: 14,
    bold: true,
    color: BRAND.primary900,
    margin: [0, 14, 0, 6],
  };
}

/** Costruisce la definizione documento pdfmake dalla scheda. */
function buildDocDefinition(s: ProgrammaResponse): TDocumentDefinitions {
  const proposte = s.proposte.filter((p) => !p.generatore);
  const idee = s.proposte.filter((p) => p.generatore);
  const dataStr = (() => {
    try {
      return new Date(s.generato_il).toLocaleString("it-IT");
    } catch {
      return s.generato_il;
    }
  })();

  const content: Content[] = [
    {
      text: `Analisi del territorio — comune ${s.comune}${s.zona ? ` · ${s.zona}` : ""}`,
      fontSize: 18,
      bold: true,
      color: BRAND.primary900,
    },
    { text: `Generata il ${dataStr}`, fontSize: 9, color: BRAND.muted, margin: [0, 2, 0, 8] },
  ];

  if (s.disclaimer?.trim()) {
    content.push({
      table: { widths: ["*"], body: [[{ text: s.disclaimer.trim(), fontSize: 8.5, italics: true, color: BRAND.muted, margin: [8, 6, 8, 6] }]] },
      layout: { hLineWidth: () => 0, vLineWidth: () => 0, fillColor: () => BRAND.bgMuted },
      margin: [0, 0, 0, 6],
    });
  }

  if (s.sintesi?.trim()) {
    content.push(sectionTitle("Quadro di sintesi"));
    content.push({ text: s.sintesi.trim(), fontSize: 10, alignment: "justify" });
  }

  const swotKeys = Object.keys(SWOT_LABEL).filter((k) => (s.swot[k]?.length ?? 0) > 0);
  if (swotKeys.length) {
    content.push(sectionTitle("Analisi SWOT"));
    for (const key of swotKeys) {
      content.push({ text: SWOT_LABEL[key], bold: true, fontSize: 11, color: BRAND.primary, margin: [0, 6, 0, 2] });
      for (const voce of s.swot[key]) {
        content.push({ text: `• ${voce.testo.trim()}`, fontSize: 9.5, margin: [0, 1, 0, 0] });
        content.push(...voce.evidenze.map(evidenzaInline));
      }
    }
  }

  content.push(sectionTitle("Proposte"));
  if (proposte.length === 0) {
    content.push({ text: "Nessuna proposta ha superato la verifica delle fonti.", italics: true, color: BRAND.muted, fontSize: 9.5 });
  } else {
    content.push(...proposte.map(propostaCard));
  }

  content.push(sectionTitle("Idee per il territorio"));
  if (s.idee_sintesi?.trim()) {
    content.push({ text: s.idee_sintesi.trim(), fontSize: 10, alignment: "justify", margin: [0, 0, 0, 4] });
  }
  content.push({
    text: "Spunti generati dagli scarti tra dati e attuato, elencati dalla più promettente.",
    fontSize: 8.5,
    italics: true,
    color: BRAND.muted,
    margin: [0, 0, 0, 6],
  });
  if (idee.length === 0) {
    content.push({ text: "Nessuna idea ha superato la verifica delle premesse.", italics: true, color: BRAND.muted, fontSize: 9.5 });
  } else {
    content.push(...idee.map(propostaCard));
  }

  if (s.citazioni.length) {
    content.push(sectionTitle("Fonti"));
    for (const c of s.citazioni) {
      const fmt = c.format ? ` (${c.format})` : "";
      content.push({
        text: [
          { text: "• " },
          { text: (c.name || c.url) + fmt, link: c.url, color: BRAND.primary, decoration: "underline" },
        ],
        fontSize: 8,
        margin: [0, 0.5, 0, 0.5],
      });
    }
  }

  return {
    pageSize: "A4",
    pageMargins: [40, 64, 40, 44],
    info: { title: `Analisi del territorio — ${s.comune}`, author: "OpenData AI" },
    header: () => ({
      margin: [40, 16, 40, 0],
      columns: [
        { svg: LOGO_MARK, width: 20, height: 20 },
        { text: "OpenData AI", bold: true, color: BRAND.primary900, fontSize: 12, margin: [6, 3, 0, 0] },
        { text: "Analisi del territorio", alignment: "right", color: BRAND.muted, fontSize: 9, margin: [0, 5, 0, 0] },
      ],
      columnGap: 0,
    }),
    footer: (currentPage: number, pageCount: number) => ({
      margin: [40, 8, 40, 0],
      columns: [
        { text: "Analisi automatica su dati pubblici · non costituisce materiale elettorale", fontSize: 7, color: BRAND.muted },
        { text: `${currentPage} / ${pageCount}`, alignment: "right", fontSize: 7, color: BRAND.muted },
      ],
    }),
    content,
    defaultStyle: { color: BRAND.text, fontSize: 10, lineHeight: 1.2 },
  };
}

/** Carica pdfmake (client-side, lazy) e ne configura i font virtuali. */
async function loadPdfMake(): Promise<typeof import("pdfmake/build/pdfmake")> {
  const pdfMakeModule = await import("pdfmake/build/pdfmake");
  const pdfFontsModule = await import("pdfmake/build/vfs_fonts");
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const pdfMake: any = (pdfMakeModule as any).default ?? pdfMakeModule;
  const fonts: any = pdfFontsModule as any;
  // Lo shape di vfs_fonts cambia tra versioni di pdfmake: copriamo i casi noti.
  pdfMake.vfs =
    fonts.pdfMake?.vfs ?? fonts.default?.pdfMake?.vfs ?? fonts.vfs ?? fonts.default?.vfs ?? pdfMake.vfs;
  /* eslint-enable @typescript-eslint/no-explicit-any */
  return pdfMake;
}

/** Innesca il download del PDF ben formattato della scheda. */
export async function downloadSchedaPdf(s: ProgrammaResponse): Promise<void> {
  const pdfMake = await loadPdfMake();
  const slug = `${s.comune}${s.zona ? `-${s.zona}` : ""}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (pdfMake as any).createPdf(buildDocDefinition(s)).download(`analisi-territorio-${slug || "report"}.pdf`);
}
