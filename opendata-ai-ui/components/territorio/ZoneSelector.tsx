"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ComuneMatch, ZonaTipo, ZoneCandidate, ZoneListResponse } from "@/lib/types";
import type { GeoLayer } from "@/components/GeoMap";

const GeoMap = dynamic(() => import("@/components/GeoMap").then((m) => m.GeoMap), {
  ssr: false,
  loading: () => (
    <div className="d-flex h-100 align-items-center justify-content-center text-muted small">
      Caricamento mappa…
    </div>
  ),
});

const TIPI: { value: ZonaTipo; label: string }[] = [
  { value: "industriale", label: "Industriale" },
  { value: "commerciale", label: "Commerciale" },
  { value: "portuale", label: "Portuale" },
  { value: "centro_storico", label: "Centro storico" },
  { value: "verde", label: "Verde" },
  { value: "agricola", label: "Agricola" },
];

const BASE_COLOR = "#0066cc";
const SELECTED_COLOR = "#d9364f";

export type ZoneSelection = {
  cod_comune: string;
  comune_nome: string;
  zona_tipo: ZonaTipo | null;
  zona_osm_id: string | null;
  zona_label: string | null;
};

function areaLabel(m2: number): string | null {
  if (!m2) return null;
  if (m2 >= 1_000_000) return `${(m2 / 1_000_000).toFixed(1)} km²`;
  return `${(m2 / 10_000).toFixed(1)} ha`;
}

/**
 * Selettore "comune → tipo zona → zona riconosciuta OSM" (spec 06).
 * Nessun disegno a mano libera: le zone sono entità OSM citabili.
 */
export function ZoneSelector({ onChange }: { onChange: (sel: ZoneSelection) => void }) {
  const { getToken } = useAuth();
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<ComuneMatch[]>([]);
  const [searching, setSearching] = useState(false);
  const [comune, setComune] = useState<ComuneMatch | null>(null);
  const [tipo, setTipo] = useState<ZonaTipo | null>(null);
  const [zones, setZones] = useState<ZoneListResponse | null>(null);
  const [loadingZones, setLoadingZones] = useState(false);
  const [zoneError, setZoneError] = useState<string | null>(null);
  const [selectedZone, setSelectedZone] = useState<ZoneCandidate | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function emit(c: ComuneMatch | null, t: ZonaTipo | null, z: ZoneCandidate | null) {
    if (!c) return;
    onChange({
      cod_comune: c.ref_istat,
      comune_nome: c.nome,
      zona_tipo: z ? t : null,
      zona_osm_id: z ? z.osm_id : null,
      zona_label: z ? (z.name ?? `${TIPI.find((x) => x.value === t)?.label} senza nome`) : null,
    });
  }

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
      try {
        const token = await getToken();
        const res = await apiFetch(`/territorio/comuni?q=${encodeURIComponent(q)}`, { token });
        if (res.ok) {
          const data = (await res.json()) as { results: ComuneMatch[] };
          setMatches(data.results.slice(0, 8));
        }
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, comune, getToken]);

  // Carica le zone quando comune + tipo sono scelti.
  useEffect(() => {
    if (!comune || !tipo) {
      setZones(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoadingZones(true);
      setZoneError(null);
      setSelectedZone(null);
      try {
        const token = await getToken();
        const params = new URLSearchParams({
          cod_comune: comune.ref_istat,
          tipo,
          comune_nome: comune.nome,
        });
        const res = await apiFetch(`/territorio/zone?${params}`, { token });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as ZoneListResponse;
        if (!cancelled) setZones(data);
      } catch (err) {
        if (!cancelled)
          setZoneError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoadingZones(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [comune, tipo, getToken]);

  const layers: GeoLayer[] = useMemo(() => {
    if (!zones) return [];
    return zones.candidates
      .filter((c) => c.geometry && (c.geometry as { type?: string }).type !== "Point")
      .map((c) => ({
        id: c.osm_id,
        name: c.name ?? c.osm_id,
        geojson: { type: "Feature", geometry: c.geometry, properties: { name: c.name } },
        color: selectedZone?.osm_id === c.osm_id ? SELECTED_COLOR : BASE_COLOR,
        visible: true,
      }));
  }, [zones, selectedZone]);

  function pickComune(m: ComuneMatch) {
    setComune(m);
    setQuery(m.nome);
    setMatches([]);
    setZones(null);
    setSelectedZone(null);
    emit(m, tipo, null);
  }

  function pickTipo(t: ZonaTipo) {
    const next = tipo === t ? null : t;
    setTipo(next);
    setSelectedZone(null);
    if (comune) emit(comune, next, null);
  }

  function pickZone(c: ZoneCandidate) {
    const next = selectedZone?.osm_id === c.osm_id ? null : c;
    setSelectedZone(next);
    if (comune) emit(comune, tipo, next);
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
          placeholder="es. Barletta"
          autoComplete="off"
          role="combobox"
          aria-expanded={matches.length > 0}
          aria-controls="comune-results"
        />
        {searching ? <div className="form-text">Ricerca…</div> : null}
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
          </div>
        ) : null}
      </div>

      {/* Tipo zona */}
      <fieldset className="mb-3" disabled={!comune}>
        <legend className="form-label fw-semibold fs-6">
          Tipo di zona <span className="fw-normal text-muted">(opzionale — senza, analisi a livello comune)</span>
        </legend>
        <div className="d-flex flex-wrap gap-2">
          {TIPI.map((t) => (
            <button
              key={t.value}
              type="button"
              className={`btn btn-sm ${tipo === t.value ? "btn-primary" : "btn-outline-primary"}`}
              aria-pressed={tipo === t.value}
              onClick={() => pickTipo(t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </fieldset>

      {/* Candidati */}
      {comune && tipo ? (
        <div className="mb-2">
          {loadingZones ? (
            <p className="small text-muted">Cerco le zone su OpenStreetMap…</p>
          ) : zoneError ? (
            <div className="alert alert-warning py-2 small mb-2">
              Ricerca zone non disponibile ({zoneError}) — l&apos;analisi procede a
              livello comunale.
            </div>
          ) : zones ? (
            <>
              {zones.fallback_level === 2 ? (
                <div className="alert alert-warning py-2 small mb-2">
                  Nessuna zona taggata su OSM: risultati dalla ricerca per nome
                  (meno precisi).
                </div>
              ) : null}
              {zones.fallback_level === 3 || zones.candidates.length === 0 ? (
                <div className="alert alert-info py-2 small mb-2">
                  Nessuna zona di questo tipo mappata nel comune: l&apos;analisi
                  procede a livello comunale. Puoi descrivere la zona nel campo
                  testuale qui sotto.
                </div>
              ) : (
                <div className="row g-2">
                  <div className="col-12 col-md-5">
                    <ul
                      className="list-group overflow-auto"
                      style={{ maxHeight: 280 }}
                      aria-label="Zone candidate"
                    >
                      {zones.candidates.map((c) => {
                        const active = selectedZone?.osm_id === c.osm_id;
                        const area = areaLabel(c.area_m2);
                        return (
                          <li key={c.osm_id}>
                            <button
                              type="button"
                              className={`list-group-item list-group-item-action ${active ? "active" : ""}`}
                              aria-pressed={active}
                              onClick={() => pickZone(c)}
                            >
                              <span className="fw-semibold">
                                {c.name ?? "(senza nome)"}
                              </span>
                              {area ? (
                                <span className={`small ms-2 ${active ? "" : "text-muted"}`}>
                                  {area}
                                </span>
                              ) : null}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                    <p className="form-text mb-0">
                      {selectedZone
                        ? "Zona selezionata — la scheda sarà mirata su quest'area."
                        : "Seleziona una zona (o nessuna per l'intero comune)."}
                    </p>
                  </div>
                  <div className="col-12 col-md-7">
                    <div
                      className="border rounded overflow-hidden"
                      style={{ height: 280 }}
                      aria-label="Mappa delle zone candidate"
                    >
                      <GeoMap
                        layers={layers}
                        focusLayerIds={selectedZone ? [selectedZone.osm_id] : undefined}
                        focusKey={selectedZone ? 1 : 0}
                      />
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
