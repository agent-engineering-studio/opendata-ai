import { describe, expect, it } from "vitest";

import { schedaToMarkdown } from "@/lib/programmaMarkdown";
import type { ProgrammaResponse } from "@/lib/types";

/** ProgrammaResponse minima con ID deterministici su idee/proposte e voci SWOT. */
function fixture(): ProgrammaResponse {
  return {
    comune: "Gioia del Colle",
    sintesi: "Quadro di sintesi.",
    swot: {
      forze: [{ id: "swot_aaa111bbb222", testo: "Patrimonio culturale diffuso", evidenze: [] }],
      debolezze: [],
      opportunita: [],
      minacce: [],
    },
    proposte: [
      {
        id: "idea_ccc333ddd444",
        titolo: "Riqualificare l'area mercatale",
        descrizione: "Intervento sull'area.",
        evidenze: [],
        fattibilita: { livello: "media", motivazione: "" },
        generatore: "gap_comparativo",
      },
      {
        id: "idea_eee555fff666",
        titolo: "Censimento beni comunali",
        descrizione: "Mappa degli asset.",
        evidenze: [],
        fattibilita: { livello: "alta", motivazione: "" },
      },
    ],
    citazioni: [],
    disclaimer: "Analisi basata su dati aperti.",
    generato_il: "2026-06-29T10:00:00.000Z",
  };
}

describe("schedaToMarkdown — ID degli item", () => {
  it("riporta l'ID di ogni proposta/idea", () => {
    const md = schedaToMarkdown(fixture());
    expect(md).toContain("`ID: idea_ccc333ddd444`");
    expect(md).toContain("`ID: idea_eee555fff666`");
  });

  it("riporta l'ID di ogni voce SWOT in coda al testo", () => {
    const md = schedaToMarkdown(fixture());
    expect(md).toContain("- Patrimonio culturale diffuso `ID: swot_aaa111bbb222`");
  });

  it("colloca l'ID della proposta subito sotto il titolo", () => {
    const md = schedaToMarkdown(fixture());
    const lines = md.split("\n");
    const titolo = lines.findIndex((l) => l.startsWith("### Riqualificare l'area mercatale"));
    expect(titolo).toBeGreaterThanOrEqual(0);
    expect(lines[titolo + 1]).toBe("`ID: idea_ccc333ddd444`");
  });

  it("è fail-safe: nessun ID se l'item non lo espone (cache vecchie)", () => {
    const s = fixture();
    delete s.proposte[0].id;
    delete s.swot.forze[0].id;
    const md = schedaToMarkdown(s);
    expect(md).not.toContain("`ID: idea_ccc333ddd444`");
    expect(md).not.toContain("`ID: swot_");
    // l'item resta comunque nel report
    expect(md).toContain("### Riqualificare l'area mercatale");
    expect(md).toContain("- Patrimonio culturale diffuso");
  });
});
