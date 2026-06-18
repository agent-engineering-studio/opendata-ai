"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ComuneMatch } from "@/lib/types";
import type { GeoLayer } from "@/components/GeoMap";

const GeoMap = dynamic(() => import("@/components/GeoMap").then((m) => m.GeoMap), {
  ssr: false,
  loading: () => (
    <div className="d-flex h-100 align-items-center justify-content-center text-muted small">
      Caricamento mappa…
    </div>
  ),
});

const BASE_COLOR = "#0066cc";

export type ZoneSelection = {
  cod_comune: string;
  comune_nome: string;
  /** OSM id del comune ("relation/123") — serve a recuperare il confine per le mappe. */
  osm_id?: string;
};

/**
 * Selettore del comune per lo studio del territorio.
 * L'unità di analisi è l'INTERO comune: niente zone, la mappa mostra il
 * confine comunale (geometria OSM via /territorio/confine).
 */
export function ZoneSelector({ onChange }: { onChange: (sel: ZoneSelection) => void }) {
  const { getToken } = useAuth();
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<ComuneMatch[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const [comune, setComune] = useState<ComuneMatch | null>(null);
  const [confine, setConfine] = useState<GeoJSON.Feature | null>(null);
  const [loadingConfine, setLoadingConfine] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Autocomplete comune (debounced).
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (q.length < 2 || (comune && q === comune.nome)) {
      setMatches([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      setSearchError(false);
      try {
        const token = await getToken();
        const res = await apiFetch(`/territorio/comuni?q=${encodeURIComponent(q)}`, { token });
        if (res.ok) {
          const data = (await res.json()) as { results: ComuneMatch[] };
          setMatches(data.results.slice(0, 8));
        } else {
          setMatches([]);
          setSearchError(true);
        }
      } catch {
        setMatches([]);
        setSearchError(true);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, comune, getToken]);

  // Carica il confine del comune selezionato (per la mappa).
  useEffect(() => {
    if (!comune?.osm_id) {
      setConfine(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoadingConfine(true);
      try {
        const token = await getToken();
        const params = new URLSearchParams({ osm_id: comune.osm_id, cod_comune: comune.ref_istat });
        const res = await apiFetch(`/territorio/confine?${params}`, { token });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { feature: GeoJSON.Feature };
        if (!cancelled) setConfine(data.feature ?? null);
      } catch {
        if (!cancelled) setConfine(null); // la mappa è un di più: l'analisi procede comunque
      } finally {
        if (!cancelled) setLoadingConfine(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [comune, getToken]);

  const layers: GeoLayer[] = useMemo(() => {
    if (!confine || !comune) return [];
    return [
      {
        id: comune.osm_id,
        name: comune.nome,
        geojson: confine,
        color: BASE_COLOR,
        visible: true,
      },
    ];
  }, [confine, comune]);

  function pickComune(m: ComuneMatch) {
    setComune(m);
    setQuery(m.nome);
    setMatches([]);
    onChange({ cod_comune: m.ref_istat, comune_nome: m.nome, osm_id: m.osm_id });
  }

  return (
    <div>
      {/* Comune */}
      <div className="position-relative mb-3" style={{ maxWidth: 420 }}>
        <label htmlFor="comune-search" className="form-label fw-semibold">
          Comune *
        </label>
        <input
          id="comune-search"
          className="form-control"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (comune && e.target.value !== comune.nome) setComune(null);
          }}
          placeholder="es. Bari"
          autoComplete="off"
          role="combobox"
          aria-expanded={matches.length > 0}
          aria-controls="comune-results"
        />
        {searching ? <div className="form-text">Ricerca…</div> : null}
        {searchError ? (
          <div className="form-text text-danger">
            Ricerca comuni momentaneamente non disponibile (OpenStreetMap non
            risponde): riprova tra poco oppure inserisci il codice ISTAT qui
            sotto.
          </div>
        ) : null}
        {matches.length > 0 ? (
          <ul
            id="comune-results"
            className="list-group position-absolute w-100 shadow"
            style={{ zIndex: 1040, top: "100%" }}
            role="listbox"
          >
            {matches.map((m) => (
              <li key={m.osm_id} role="option" aria-selected="false">
                <button
                  type="button"
                  className="list-group-item list-group-item-action"
                  onClick={() => pickComune(m)}
                >
                  {m.nome}{" "}
                  <span className="text-muted small">ISTAT {m.ref_istat}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {comune ? (
          <div className="form-text">
            Selezionato: <strong>{comune.nome}</strong> (ISTAT {comune.ref_istat})
            {" "}— l&apos;analisi riguarda l&apos;intero comune.
          </div>
        ) : null}
      </div>

      {/* Mappa del confine comunale */}
      {comune ? (
        <div
          className="border rounded overflow-hidden mb-2"
          style={{ height: 300 }}
          aria-label={`Mappa del comune di ${comune.nome}`}
        >
          {loadingConfine ? (
            <div className="d-flex h-100 align-items-center justify-content-center text-muted small">
              Carico il confine del comune…
            </div>
          ) : layers.length > 0 ? (
            <GeoMap layers={layers} focusLayerIds={[comune.osm_id]} focusKey={1} />
          ) : (
            <div className="d-flex h-100 align-items-center justify-content-center text-muted small text-center px-3">
              Confine non disponibile in mappa (OpenStreetMap non risponde) —
              l&apos;analisi procede comunque a livello comunale.
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
