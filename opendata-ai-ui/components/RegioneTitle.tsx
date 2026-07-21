"use client";

/*
 * Titolo esplicativo globale: rende SEMPRE chiaro su quale regione opera il
 * cruscotto di monitoraggio. La regione è fissata per deployment (una regione
 * per installazione, #191); nella static export (R6) la si imposta al build con
 * NEXT_PUBLIC_REGION_NAME, coerente con REGION del backend. Non impostata (dev
 * o installazione non ancora scoping) → il titolo non si mostra.
 *
 * Diverso dal RegioneBadge di /territorio (fetch runtime auth-gated): questo è
 * un titolo statico, visibile anche a visitatori non autenticati e sulla vista
 * pubblica.
 */

const REGION = process.env.NEXT_PUBLIC_REGION_NAME?.trim();

export function RegioneTitle() {
  if (!REGION) return null;
  return (
    <div
      className="d-flex flex-wrap align-items-baseline gap-2 py-2 border-top"
      style={{ borderColor: "var(--color-border)" }}
      aria-label={`Cruscotto open data della Regione ${REGION}`}
    >
      <strong style={{ fontSize: 15 }}>
        <span aria-hidden="true">📍 </span>
        Cruscotto Open Data · Regione {REGION}
      </strong>
      <span className="text-muted" style={{ fontSize: 13 }}>
        Monitoraggio della maturità e del riuso dei dati aperti dei comuni
      </span>
    </div>
  );
}
