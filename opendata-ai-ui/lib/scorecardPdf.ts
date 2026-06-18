/*
 * Export PDF della Scorecard di maturità open-data (o, se i dati sono insufficienti,
 * della guida operativa open-data). PDF vettoriale via pdfmake, caricato con import
 * dinamico (la UI è `output: 'export'`, niente runtime server; carico solo al click).
 */
import type { Content, TDocumentDefinitions } from "pdfmake/interfaces";

const BRAND = {
  primary: "#0066cc",
  primary900: "#002b56",
  text: "#17324d",
  muted: "#5b6f82",
  green: "#00cf86",
  border: "#e3e4e6",
  bgMuted: "#f5f5f5",
};

const LOGO_MARK = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect width="48" height="48" rx="11" fill="#0066cc"/><path d="M24 9c-7.18 0-13 5.6-13 12.5C11 31 24 40 24 40s13-9 13-18.5C37 14.6 31.18 9 24 9z" fill="#ffffff"/><circle cx="24" cy="21.5" r="5" fill="#00cf86"/></svg>`;

export type GuidaPasso = {
  titolo: string;
  descrizione: string;
  riferimenti?: { label: string; url: string }[];
};
export type Guida = {
  titolo: string;
  premessa: string;
  passi: GuidaPasso[];
  riferimenti: { label: string; url: string }[];
  nota?: string;
};
export type ScorecardData = {
  entity: { name: string; type?: string | null; region?: string | null };
  level: string;
  overall: number;
  dimensions: { policy: number; portal: number; quality: number; impact: number };
  n_datasets: number | null;
  insufficient_data?: boolean;
  guida?: Guida | null;
  recommendations?: { severity: string; dimension: string; message: string }[];
};

async function loadPdfMake(): Promise<typeof import("pdfmake/build/pdfmake")> {
  const pdfMakeModule = await import("pdfmake/build/pdfmake");
  const pdfFontsModule = await import("pdfmake/build/vfs_fonts");
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const pdfMake: any = (pdfMakeModule as any).default ?? pdfMakeModule;
  const fonts: any = pdfFontsModule as any;
  pdfMake.vfs =
    fonts.pdfMake?.vfs ?? fonts.default?.pdfMake?.vfs ?? fonts.vfs ?? fonts.default?.vfs ?? pdfMake.vfs;
  /* eslint-enable @typescript-eslint/no-explicit-any */
  return pdfMake;
}

function header(): Content {
  return {
    columns: [
      { svg: LOGO_MARK, width: 28, height: 28 },
      { text: "OpenData AI", margin: [8, 6, 0, 0], bold: true, color: BRAND.primary900 },
      { text: "Maturità open data", alignment: "right", margin: [0, 6, 0, 0], color: BRAND.muted },
    ],
    margin: [0, 0, 0, 12],
  };
}

function guidaContent(g: Guida): Content[] {
  const out: Content[] = [
    { text: g.titolo, fontSize: 16, bold: true, color: BRAND.primary900, margin: [0, 4, 0, 6] },
    { text: g.premessa, color: BRAND.text, margin: [0, 0, 0, 10] },
  ];
  g.passi.forEach((p) => {
    out.push({ text: p.titolo, bold: true, color: BRAND.primary, margin: [0, 6, 0, 2] });
    out.push({ text: p.descrizione, color: BRAND.text, fontSize: 10 });
    (p.riferimenti ?? []).forEach((r) =>
      out.push({ text: r.label, link: r.url, color: BRAND.primary, fontSize: 9, margin: [0, 1, 0, 0] }),
    );
  });
  if (g.nota) out.push({ text: g.nota, italics: true, color: BRAND.muted, fontSize: 9, margin: [0, 12, 0, 0] });
  return out;
}

const LEVEL_FILL: Record<string, string> = {
  Beginner: "#dc2626",
  Follower: "#d97706",
  "Fast-tracker": "#2563eb",
  "Trend-setter": "#00cf86",
};

function scorecardContent(s: ScorecardData, radarPng?: string): Content[] {
  const dim = s.dimensions;
  return [
    { text: s.entity.name, fontSize: 16, bold: true, color: BRAND.primary900, margin: [0, 4, 0, 4] },
    // Badge livello colorato (es. "Fast-tracker · 67/100") — riprodotto come cella riempita.
    {
      table: {
        widths: ["auto"],
        body: [
          [
            {
              text: `${s.level} · ${Math.round(s.overall)}/100`,
              color: "white",
              bold: true,
              fillColor: LEVEL_FILL[s.level] ?? BRAND.primary900,
              margin: [8, 4, 8, 4],
            },
          ],
        ],
      },
      layout: "noBorders",
      margin: [0, 0, 0, 8],
    },
    {
      text: `${s.entity.type ?? "ente"}${s.entity.region ? ` · ${s.entity.region}` : ""} · ${s.n_datasets ?? 0} dataset valutati`,
      color: BRAND.muted,
      fontSize: 10,
      margin: [0, 0, 0, 10],
    },
    // Grafico radar delle 4 dimensioni (immagine catturata dalla pagina).
    ...(radarPng
      ? [{ image: radarPng, width: 280, alignment: "center", margin: [0, 0, 0, 10] } as Content]
      : []),
    { text: "Dimensioni (0–100)", bold: true, color: BRAND.primary900, margin: [0, 4, 0, 4] },
    {
      table: {
        widths: ["*", 50],
        body: [
          ["Policy", String(Math.round(dim.policy))],
          ["Portale", String(Math.round(dim.portal))],
          ["Qualità", String(Math.round(dim.quality))],
          ["Impatto", String(Math.round(dim.impact))],
        ],
      },
      layout: "lightHorizontalLines",
      margin: [0, 0, 0, 10],
    },
    ...(s.recommendations && s.recommendations.length
      ? [
          { text: "Raccomandazioni", bold: true, color: BRAND.primary900, margin: [0, 4, 0, 4] } as Content,
          {
            ul: s.recommendations.map((r) => `[${r.severity}] ${r.message} — ${r.dimension}`),
            fontSize: 10,
            color: BRAND.text,
          } as Content,
        ]
      : []),
  ];
}

function buildDoc(s: ScorecardData, radarPng?: string): TDocumentDefinitions {
  const body: Content[] =
    s.insufficient_data && s.guida ? guidaContent(s.guida) : scorecardContent(s, radarPng);
  return {
    pageSize: "A4",
    pageMargins: [48, 48, 48, 56],
    defaultStyle: { fontSize: 11, color: BRAND.text },
    content: [header(), ...body],
    footer: (current: number, total: number) => ({
      columns: [
        {
          text: "Maturità open data · dati pubblici · a soli fini costruttivi, non materiale elettorale",
          color: BRAND.muted,
          fontSize: 8,
          margin: [48, 8, 0, 0],
        },
        { text: `${current}/${total}`, alignment: "right", color: BRAND.muted, fontSize: 8, margin: [0, 8, 48, 0] },
      ],
    }),
  };
}

export async function downloadScorecardPdf(s: ScorecardData, radarPng?: string): Promise<void> {
  const pdfMake = await loadPdfMake();
  const slug = (s.entity.name || "ente")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (pdfMake as any).createPdf(buildDoc(s, radarPng)).download(`maturita-${slug || "ente"}.pdf`);
}
