# Spec 05 — Frontend pagina "Territorio" (Next.js)

**Pezzo 5.** La UI del verticale PA: la pagina **`/territorio`** ("Studio del
territorio") che chiama `POST /programma` (Pezzo 4) e mostra la scheda — SWOT,
proposte con fattibilità, e **citazioni cliccabili** verso le fonti. Rispetta i
vincoli del repo: static export, `apiFetch`, niente `app/api/*`.

> **Naming.** Route `app/territorio/`, label di navigazione "Territorio", titolo in
> pagina "Studio del territorio". Non usare "esplora": la route `/esplora`
> (chat+mappa unificata) esiste già. La pagina è progettata per ospitare nei pezzi
> successivi il **selettore di zona OSM** (Pezzo 6, in testa) e il **tab
> Scheda | Idee** (Pezzo 8, sui risultati): lasciare lo spazio strutturale (header
> di selezione + area risultati), senza implementarli qui.

## Vincoli del repo (dal CLAUDE.md / codice)

- **R6** — `output: 'export'`: nessuna route API lato Next. Ogni chiamata passa per
  `lib/api.ts::apiFetch()` con Bearer token Clerk da `lib/auth.ts::useAuth().getToken()`.
- Pagina = client component (`'use client'`) sotto `app/territorio/page.tsx`, sul
  modello di `app/mappa/`.
- Componenti in `components/`, tipi in `lib/types.ts`.
- File esterni (se servono) via `proxyFetch` — ma le citazioni del programma sono
  link diretti a URL risolvibili (API OpenCoesione, dataset ISTAT), quindi
  normalmente bastano `<a href>` con `target="_blank" rel="noreferrer"`.

## Tipi (`lib/types.ts`)

- Estendere `ResourceSource` con `"opencoesione" | "osm"` (oggi solo
  ckan/istat/eurostat/oecd).
- Aggiungere i tipi che rispecchiano il contratto Pydantic del Pezzo 4:
  `Evidenza`, `VoceSwot`, `Fattibilita`, `Proposta`, `ProgrammaRequest`,
  `ProgrammaResponse` (vedi `docs/specs/04-programma-endpoint.md` §6).

## Pagina `app/territorio/page.tsx`

1. **Form di input** (sobrio, accessibile):
   - `cod_comune` (codice ISTAT) — campo obbligatorio; opzionale un piccolo helper
     testuale "nome comune → codice" rimandato (lookup ISTAT in pezzo successivo);
   - `zona` (testo libero, es. "area industriale") e `tema` opzionali;
   - bottone "Genera scheda".
2. **Chiamata**: `apiFetch("/programma", { method: "POST", token, body })`; in
   alternativa consumare `/programma/stream` (NDJSON) per mostrare lo stato per fonte
   (start/end di istat, opencoesione, programma) come fa la pagina mappa.
3. **Stati**: loading con indicazione delle fonti in corso; errore; risultato.
4. **Render del risultato** (vedi componenti sotto).
5. **Export PDF**: pulsante "Esporta PDF" via `window.print()` con un foglio di stile
   `@media print` dedicato (nessun server, coerente con static export). Librerie più
   pesanti (html2pdf) opzionali e rimandabili.

## Componenti (`components/territorio/`)

- `SwotGrid.tsx` — 4 quadranti (Forze / Debolezze / Opportunità / Minacce); ogni voce
  mostra il `testo` e, sotto, le `evidenze` come `CitationLink`.
- `ProposalCard.tsx` — titolo, descrizione, `FeasibilityBadge`, eventuale blocco
  finanziamento (linea + stato + link fonte), elenco `evidenze`.
- `FeasibilityBadge.tsx` — badge per `alta/media/bassa/da_verificare` (colore +
  etichetta; `da_verificare` evidente, non "verde").
- `CitationLink.tsx` — rende una `Evidenza`: `fonte` (chip: ISTAT/OpenCoesione/…),
  `dettaglio`, e `url` come link esterno. È il cuore "verificabile": ogni claim ha qui
  la sua fonte cliccabile.
- `DisclaimerBanner.tsx` — mostra `disclaimer` in evidenza (è obbligatorio dal Pezzo 4).
- `SourcesList.tsx` — opzionale, elenco completo `citazioni` in fondo.

## Navigazione e contenuti

- Link alla pagina nella nav (`components/SiteHeader.tsx`, label "Territorio") e
  nella home (`app/page.tsx`).
- Nota in pagina: l'output è **analisi basata su dati pubblici**, non materiale
  elettorale; coerente con `note-legali` e con il disclaimer del backend.

## Accessibilità (il repo ha già una pagina `accessibilita`)

- HTML semantico (heading hierarchy, liste), label sui campi, focus visibile,
  contrasto adeguato, badge non basati solo sul colore (anche etichetta testuale).

## Definition of Done

- [ ] `lib/types.ts` esteso (ResourceSource + tipi Programma).
- [ ] `app/territorio/page.tsx` con form, chiamata `apiFetch` (token Clerk), stati
      loading/errore/risultato.
- [ ] Componenti `SwotGrid`, `ProposalCard`, `FeasibilityBadge`, `CitationLink`,
      `DisclaimerBanner`.
- [ ] Citazioni cliccabili verso URL risolvibili; disclaimer sempre visibile.
- [ ] Export PDF via `window.print()` + stile `@media print`.
- [ ] Nessun `app/api/*`; build statica `next build` (output export) verde;
      lint (`eslint`) pulito.
- [ ] Link in navigazione; pagina accessibile da tastiera.
- [ ] Smoke manuale: comune pugliese reale → scheda con SWOT, proposte, fattibilità e
      fonti che si aprono davvero.
