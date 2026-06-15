# Prompt Claude Code — P05: frontend pagina "Territorio"

> Eseguire dalla root di `opendata-ai`, **dopo** il Pezzo 4 (endpoint `/programma`
> attivo). Leggi `CLAUDE.md` (**R6** static export, R7 auth) e
> `docs/specs/05-frontend-programma.md`. Lavori in `opendata-ai-ui/`.

---

Costruisci la pagina UI del verticale PA — route **`app/territorio/`**, label nav
**"Territorio"**, titolo in pagina **"Studio del territorio"** (NON "esplora": la
route `/esplora` esiste già): chiama `POST /programma` e mostra la scheda
(SWOT + proposte + **citazioni cliccabili**). Static export (`output: 'export'`):
**niente** route `app/api/*`; ogni chiamata via `lib/api.ts::apiFetch()` con Bearer
token da `lib/auth.ts::useAuth().getToken()`.
Progetta il layout per ospitare in futuro il selettore di zona (Pezzo 6, header) e
il toggle Scheda|Idee (Pezzo 8, sui risultati) — solo spazio strutturale, non
implementarli qui.

Studia prima e ricalca: `app/mappa/` (pagina client che chiama il backend, gestisce
token + stati loading/errore, e — se presente — consuma lo stream NDJSON),
`lib/api.ts` (`apiFetch`, `proxyFetch`), `lib/auth.ts` (`useAuth`), `lib/types.ts`
(tipi e `ResourceSource`), `components/` (stile dei componenti esistenti),
`app/layout.tsx` e `app/page.tsx` (nav).

## Modifiche

1. **`lib/types.ts`**
   - Estendi `ResourceSource` con `"opencoesione" | "osm"`.
   - Aggiungi i tipi del contratto del Pezzo 4 (`Evidenza`, `VoceSwot`, `Fattibilita`,
     `Proposta`, `ProgrammaRequest`, `ProgrammaResponse`) — vedi
     `docs/specs/04-programma-endpoint.md` §6.

2. **`app/territorio/page.tsx`** (client component, `'use client'`)
   - Form: `cod_comune` (obbligatorio), `zona` e `tema` (opzionali), bottone "Genera
     scheda". Label associate, focus visibile.
   - Chiamata: `apiFetch("/programma", { method: "POST", token, body: JSON })`.
     Opzionale: consuma `/programma/stream` (NDJSON) per mostrare lo stato per fonte,
     ricalcando il reader della pagina mappa.
   - Stati: loading (con fonti in corso se streaming), errore, risultato.
   - Pulsante "Esporta PDF" → `window.print()`; aggiungi regole `@media print` (in
     `globals.css` o stile locale) per una resa pulita della scheda.
   - Nota in pagina: "analisi basata su dati pubblici, non materiale elettorale".

3. **`components/territorio/`**
   - `SwotGrid.tsx` — 4 quadranti Forze/Debolezze/Opportunità/Minacce; ogni voce con
     `testo` + `evidenze` (via `CitationLink`).
   - `ProposalCard.tsx` — titolo, descrizione, `FeasibilityBadge`, blocco
     finanziamento (linea/stato/link fonte) se presente, elenco `evidenze`.
   - `FeasibilityBadge.tsx` — `alta|media|bassa|da_verificare`; colore **+ etichetta
     testuale** (non solo colore); `da_verificare` chiaramente non "ok".
   - `CitationLink.tsx` — rende `Evidenza`: chip `fonte`, `dettaglio`, `url` come
     link esterno (`target="_blank" rel="noreferrer"`).
   - `DisclaimerBanner.tsx` — mostra `disclaimer` in evidenza.
   - (opz.) `SourcesList.tsx` — elenco completo `citazioni` in fondo.

4. **Navigazione** — aggiungi `{ href: "/territorio", label: "Territorio" }` in
   `components/SiteHeader.tsx` e il link in `app/page.tsx` se la home elenca le
   funzionalità.

## Vincoli

- **R6**: nessun `app/api/*`; tutto via `apiFetch`. **R7**: token Clerk come nelle
  altre pagine (in dev senza Clerk, `getToken()` torna null ed è gestito).
- Accessibilità (il repo ha già `app/accessibilita`): HTML semantico, label, focus,
  contrasto, badge non solo-colore.
- Niente selettore di zona qui (è il Pezzo 6, `06-zone-osm.md`): `zona` è un campo
  testo; `zona_tipo`/`zona_osm_id` non vanno esposti nel form.
- Coerenza con lo stile dei componenti esistenti (non introdurre un design system nuovo).

## Output atteso

`lib/types.ts` esteso, `app/territorio/page.tsx`, i componenti sotto
`components/territorio/`, link in nav, export PDF via print. `next build` (export)
verde, `eslint` pulito, nessun `app/api/*`. Smoke manuale: comune pugliese reale →
scheda con SWOT, proposte, fattibilità e fonti che si aprono. Riepiloga per aggiornare
la spec.
