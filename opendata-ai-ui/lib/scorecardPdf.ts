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
export type DimensionBreakdown = {
  dimension: string;
  label: string;
  score: number;
  description: string;
  drivers: { label: string; value: number }[];
  weakest: string[];
};
export type Sector = {
  code: string;
  label: string;
  n_datasets: number;
  is_core: boolean;
  present: boolean;
  priority: number | null;
};
export type Coverage = {
  entity_type: string;
  coverage_score: number;
  sectors: Sector[];
  missing_core: Sector[];
  hvd_present: string[];
  hvd_missing: string[];
};
type Dimensions = { policy: number; portal: number; quality: number; impact: number };

export type AzioneGap = {
  code: string;
  dimension_label: string;
  severity: string;
  messaggio: string;
  sul_collo_di_bottiglia: boolean;
};
export type Gap = {
  livello_attuale: string;
  prossimo_livello: string | null;
  punti_al_prossimo: number | null;
  collo_di_bottiglia_label: string;
  quick_win: AzioneGap[];
  strategiche: AzioneGap[];
};
export type PeerComparison = {
  cluster_label: string;
  count: number;
  rank: number | null;
  better_than_pct: number | null;
  median_overall: number;
  median_dimensions: Dimensions;
};
export type Portfolio = {
  count: number;
  pct_hvd: number | null;
  pct_open_license: number | null;
  avg_freshness_days: number | null;
  avg_stars: number | null;
  avg_reuse: number | null;
};
export type ImprovementLeva = {
  key: string;
  label: string;
  score: number;
  potential: number;
  recs: { code: string; message: string }[];
};
export type Improvements = {
  leve: ImprovementLeva[];
  nextLevel: { name: string; gap: number } | null;
};

export type ScorecardData = {
  entity: { name: string; type?: string | null; region?: string | null };
  level: string;
  overall: number;
  dimensions: Dimensions;
  n_datasets: number | null;
  insufficient_data?: boolean;
  guida?: Guida | null;
  recommendations?: { severity: string; dimension: string; message: string }[];
  dimension_breakdown?: DimensionBreakdown[];
  coverage?: Coverage | null;
  gap?: Gap | null;
  peer_comparison?: PeerComparison | null;
  unmet_reuse_demand?: { count: number; items: string[]; penalty: number };
};

const DIM_LABEL: Record<string, string> = {
  policy: "Policy",
  portal: "Portale",
  quality: "Qualità",
  impact: "Impatto",
};

/** Opzioni dell'export: immagine del radar + dati ausiliari resi sulla pagina HTML. */
export type ScorecardPdfExtras = {
  radarPng?: string;
  portfolio?: Portfolio | null;
  improvements?: Improvements;
};

// Etichette HVD allineate a opendata_core.maturity.coverage.HVD_LABELS.
const HVD_LABELS: Record<string, string> = {
  geospatial: "Geospaziale",
  earth_observation_environment: "Osservazione della Terra e ambiente",
  meteorological: "Meteorologici",
  statistics: "Statistici",
  companies_ownership: "Imprese e proprietà",
  mobility: "Mobilità",
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

function scorecardContent(s: ScorecardData, extras: ScorecardPdfExtras): Content[] {
  const dim = s.dimensions;
  const { radarPng, portfolio, improvements } = extras;
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
    ...peerComparisonContent(s.peer_comparison, dim),
    ...gapContent(s.gap),
    ...breakdownContent(s.dimension_breakdown),
    ...coverageContent(s.coverage),
    ...portfolioContent(portfolio),
    ...improvementsContent(improvements),
    ...(s.recommendations && s.recommendations.length
      ? [
          { text: "Raccomandazioni e come colmarle", bold: true, color: BRAND.primary900, margin: [0, 8, 0, 4] } as Content,
          {
            ul: s.recommendations.map((r) => `[${r.severity}] ${r.message} — ${r.dimension}`),
            fontSize: 10,
            color: BRAND.text,
          } as Content,
        ]
      : []),
    ...unmetReuseContent(s.unmet_reuse_demand),
  ];
}

/** Confronto con enti simili: posizione nel cluster + per dimensione vs mediana. */
function peerComparisonContent(pc: PeerComparison | null | undefined, dim: Dimensions): Content[] {
  if (!pc) return [];
  const pos =
    pc.rank != null
      ? `${pc.rank}° posto su ${pc.count}${pc.better_than_pct != null ? ` (meglio del ${pc.better_than_pct}% dei pari)` : ""}`
      : `gruppo di ${pc.count} enti`;
  return [
    { text: "Confronto con enti simili", bold: true, color: BRAND.primary900, margin: [0, 8, 0, 4] },
    {
      text: `Tra i «${pc.cluster_label}»: ${pos}. Mediana del gruppo: ${Math.round(pc.median_overall)}/100.`,
      color: BRAND.muted,
      fontSize: 10,
      margin: [0, 0, 0, 4],
    },
    {
      table: {
        widths: ["*", 50, 60, 50],
        body: [
          [
            { text: "Dimensione", bold: true, fontSize: 9, color: BRAND.muted },
            { text: "Ente", bold: true, fontSize: 9, color: BRAND.muted, alignment: "center" as const },
            { text: "Mediana", bold: true, fontSize: 9, color: BRAND.muted, alignment: "center" as const },
            { text: "Δ", bold: true, fontSize: 9, color: BRAND.muted, alignment: "center" as const },
          ],
          ...(["policy", "portal", "quality", "impact"] as const).map((k) => {
            const delta = Math.round(dim[k] - pc.median_dimensions[k]);
            return [
              { text: DIM_LABEL[k], fontSize: 9, color: BRAND.text },
              { text: String(Math.round(dim[k])), fontSize: 9, alignment: "center" as const },
              { text: String(Math.round(pc.median_dimensions[k])), fontSize: 9, alignment: "center" as const, color: BRAND.muted },
              {
                text: delta > 0 ? `+${delta}` : String(delta),
                fontSize: 9,
                alignment: "center" as const,
                color: delta > 0 ? BRAND.green : delta < 0 ? "#dc2626" : BRAND.muted,
              },
            ];
          }),
        ],
      },
      layout: "lightHorizontalLines",
      margin: [0, 0, 0, 6],
    },
  ];
}

/** Le mosse che contano di più: prossimo livello, collo di bottiglia, quick-win vs strategiche. */
function gapContent(gap: Gap | null | undefined): Content[] {
  if (!gap || (gap.quick_win.length === 0 && gap.strategiche.length === 0)) return [];
  const intro =
    gap.prossimo_livello && gap.punti_al_prossimo != null
      ? `Da ${gap.livello_attuale} a ${gap.prossimo_livello} mancano ${Math.round(gap.punti_al_prossimo)} punti. Collo di bottiglia: ${gap.collo_di_bottiglia_label}.`
      : `Livello massimo (${gap.livello_attuale}). Margine residuo più ampio su ${gap.collo_di_bottiglia_label}.`;
  const azione = (a: AzioneGap) =>
    `[${a.severity}] ${a.messaggio} — ${a.dimension_label}${a.sul_collo_di_bottiglia ? " ⚑" : ""}`;
  const out: Content[] = [
    { text: "Le mosse che contano di più", bold: true, color: BRAND.primary900, margin: [0, 8, 0, 4] },
    { text: intro, color: BRAND.muted, fontSize: 10, margin: [0, 0, 0, 4] },
  ];
  if (gap.quick_win.length) {
    out.push({ text: "Facili e rapide", bold: true, color: BRAND.text, fontSize: 10, margin: [0, 2, 0, 2] });
    out.push({ ul: gap.quick_win.map(azione), fontSize: 9, color: BRAND.text });
  }
  if (gap.strategiche.length) {
    out.push({ text: "Strategiche", bold: true, color: BRAND.text, fontSize: 10, margin: [0, 4, 0, 2] });
    out.push({ ul: gap.strategiche.map(azione), fontSize: 9, color: BRAND.text });
  }
  return out;
}

/** Valore del patrimonio: KPI sintetici dei dataset valutati. */
function portfolioContent(pf: Portfolio | null | undefined): Content[] {
  if (!pf || pf.count <= 0) return [];
  const pct = (v: number | null) => (v != null ? `${Math.round(v)}%` : "—");
  const num = (v: number | null) => (v != null ? v.toFixed(1) : "—");
  return [
    { text: "Valore del patrimonio", bold: true, color: BRAND.primary900, margin: [0, 8, 0, 4] },
    {
      table: {
        widths: ["*", "*", "*", "*", "*"],
        body: [
          [
            { text: "Dataset", bold: true, fontSize: 9, color: BRAND.muted, alignment: "center" as const },
            { text: "Alto valore (HVD)", bold: true, fontSize: 9, color: BRAND.muted, alignment: "center" as const },
            { text: "Licenza aperta", bold: true, fontSize: 9, color: BRAND.muted, alignment: "center" as const },
            { text: "Stelle medie", bold: true, fontSize: 9, color: BRAND.muted, alignment: "center" as const },
            { text: "Riuso medio", bold: true, fontSize: 9, color: BRAND.muted, alignment: "center" as const },
          ],
          [
            { text: String(pf.count), fontSize: 11, alignment: "center" as const, color: BRAND.primary },
            { text: pct(pf.pct_hvd), fontSize: 11, alignment: "center" as const, color: BRAND.primary },
            { text: pct(pf.pct_open_license), fontSize: 11, alignment: "center" as const, color: BRAND.primary },
            { text: num(pf.avg_stars), fontSize: 11, alignment: "center" as const, color: BRAND.primary },
            { text: num(pf.avg_reuse), fontSize: 11, alignment: "center" as const, color: BRAND.primary },
          ],
        ],
      },
      layout: "lightHorizontalLines",
      margin: [0, 0, 0, 6],
    },
  ];
}

/** Come migliorare: leve ordinate per impatto sul punteggio complessivo. */
function improvementsContent(imp: Improvements | undefined): Content[] {
  if (!imp || imp.leve.length === 0) return [];
  const out: Content[] = [
    { text: "Come migliorare", bold: true, color: BRAND.primary900, margin: [0, 8, 0, 4] },
  ];
  if (imp.nextLevel) {
    out.push({
      text: `Mancano ${Math.round(imp.nextLevel.gap)} punti per il livello ${imp.nextLevel.name}. Interventi a maggiore impatto:`,
      color: BRAND.muted,
      fontSize: 10,
      margin: [0, 0, 0, 4],
    });
  }
  imp.leve.forEach((l) => {
    out.push({
      text: [
        { text: `+${Math.round(l.potential)} pti · ${l.label}`, bold: true, color: BRAND.text },
        { text: `  (oggi ${Math.round(l.score)}/100)`, color: BRAND.muted, fontSize: 9 },
      ],
      fontSize: 10,
      margin: [0, 4, 0, 1],
    });
    if (l.recs.length) {
      out.push({ ul: l.recs.map((r) => r.message), fontSize: 9, color: BRAND.text });
    }
  });
  return out;
}

/** Domanda di riuso non soddisfatta (anello valore⇄maturità). */
function unmetReuseContent(unmet: ScorecardData["unmet_reuse_demand"]): Content[] {
  if (!unmet || unmet.count <= 0) return [];
  return [
    { text: "Domanda di riuso non soddisfatta", bold: true, color: BRAND.primary900, margin: [0, 8, 0, 4] },
    {
      text: "Le analisi di Territorio segnalano dati richiesti ma non ancora pubblicati: questi gap riducono l'Impatto.",
      color: BRAND.muted,
      fontSize: 10,
      margin: [0, 0, 0, 4],
    },
    { ul: unmet.items, fontSize: 9, color: BRAND.text },
  ];
}

/** Spiegazione per dimensione: cosa misura + sotto-metriche (dalla più debole). */
function breakdownContent(breakdown?: DimensionBreakdown[]): Content[] {
  if (!breakdown || !breakdown.length) return [];
  const out: Content[] = [
    { text: "Come si legge il punteggio", bold: true, color: BRAND.primary900, margin: [0, 8, 0, 4] },
  ];
  breakdown.forEach((b) => {
    out.push({
      text: [
        { text: `${b.label} · ${Math.round(b.score)}/100`, bold: true, color: BRAND.text },
        { text: `  ${b.description}`, color: BRAND.muted, fontSize: 9 },
      ],
      margin: [0, 4, 0, 1],
      fontSize: 10,
    });
    out.push({
      text: b.drivers
        .map((d) => `${b.weakest.includes(d.label) ? "⚠ " : ""}${d.label} ${Math.round(d.value)}`)
        .join("   ·   "),
      color: BRAND.muted,
      fontSize: 9,
    });
  });
  return out;
}

/** Copertura per settore + categorie HVD + cosa manca per una collection ottimale. */
function coverageContent(coverage?: Coverage | null): Content[] {
  if (!coverage) return [];
  const core = coverage.sectors.filter((sec) => sec.is_core);
  const out: Content[] = [
    { text: "Copertura per settore", bold: true, color: BRAND.primary900, margin: [0, 8, 0, 4] },
    {
      text: `Copertura ${Math.round(coverage.coverage_score)}% dei settori chiave attesi per un ente di tipo «${coverage.entity_type}» (${core.filter((sec) => sec.present).length}/${core.length}).`,
      color: BRAND.muted,
      fontSize: 10,
      margin: [0, 0, 0, 4],
    },
    {
      table: {
        widths: ["*", 60, 40],
        body: [
          [
            { text: "Settore", bold: true, fontSize: 9, color: BRAND.muted },
            { text: "Dataset", bold: true, fontSize: 9, color: BRAND.muted },
            { text: "", fontSize: 9 },
          ],
          ...core.map((sec) => [
            { text: `${sec.present ? "" : "⚠ "}${sec.label}`, fontSize: 9, color: sec.present ? BRAND.text : "#b45309" },
            { text: String(sec.n_datasets), fontSize: 9, alignment: "center" as const },
            { text: sec.present ? "✓" : "—", fontSize: 9, alignment: "center" as const, color: sec.present ? BRAND.green : BRAND.muted },
          ]),
        ],
      },
      layout: "lightHorizontalLines",
      margin: [0, 0, 0, 6],
    },
    {
      text: `Dati ad elevato valore (HVD) · ${coverage.hvd_present.length}/6: ${
        coverage.hvd_present.map((h) => HVD_LABELS[h] ?? h).join(", ") || "nessuna categoria coperta"
      }.`,
      fontSize: 9,
      color: BRAND.muted,
    },
  ];
  if (coverage.missing_core.length) {
    out.push({
      text: "Cosa manca per una collection ottimale (per priorità):",
      bold: true,
      color: BRAND.text,
      fontSize: 10,
      margin: [0, 6, 0, 2],
    });
    out.push({
      ol: coverage.missing_core.map((sec) => sec.label),
      fontSize: 9,
      color: BRAND.text,
    });
  }
  return out;
}

function buildDoc(s: ScorecardData, extras: ScorecardPdfExtras): TDocumentDefinitions {
  const body: Content[] =
    s.insufficient_data && s.guida ? guidaContent(s.guida) : scorecardContent(s, extras);
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

export async function downloadScorecardPdf(
  s: ScorecardData,
  extras: ScorecardPdfExtras = {},
): Promise<void> {
  const pdfMake = await loadPdfMake();
  const slug = (s.entity.name || "ente")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (pdfMake as any).createPdf(buildDoc(s, extras)).download(`maturita-${slug || "ente"}.pdf`);
}
