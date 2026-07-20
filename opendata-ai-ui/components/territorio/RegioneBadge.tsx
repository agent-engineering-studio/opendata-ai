"use client";

/*
 * Badge "Regione: <nome>" — rende visibile all'utente su quale regione opera il
 * deployment (issue #191, F5). Deriva dalla config del backend (`REGION` →
 * /territorio/regione): l'autocomplete dei comuni è già ristretto alla stessa
 * regione. In dev (nessuno scope configurato) `scoped=false` → il badge non si
 * mostra. Best-effort: un errore di rete non rompe la pagina.
 */

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type RegioneInfo = {
  scoped: boolean;
  cod_regione: string | null;
  nome: string | null;
  province: string[];
};

export function RegioneBadge() {
  const { getToken } = useAuth();
  const [info, setInfo] = useState<RegioneInfo | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const token = await getToken();
        const res = await apiFetch("/territorio/regione", { token });
        if (res.ok && alive) setInfo(await res.json());
      } catch {
        /* il badge è un di più: la pagina funziona comunque */
      }
    })();
    return () => {
      alive = false;
    };
  }, [getToken]);

  if (!info || !info.scoped) return null;

  const label = info.nome
    ? `Regione: ${info.nome}`
    : `Ambito: ${info.province.length} province`;
  const title = info.province.length
    ? `Ricerca, territorio e analisi filtrati su ${info.nome ?? "queste province"} (province ISTAT: ${info.province.join(", ")}).`
    : undefined;

  return (
    <span
      className="badge rounded-pill bg-primary-subtle text-primary-emphasis border border-primary-subtle mb-2"
      title={title}
      aria-label={label}
    >
      <span aria-hidden="true">📍 </span>
      {label}
    </span>
  );
}
