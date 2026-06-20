"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useAuth } from "@/lib/auth";
import type { ChatMessage, ChatRequest, Resource } from "@/lib/types";
import type { GeoLayer } from "@/components/GeoMap";
import { apiFetch } from "@/lib/api";
import { resourceToGeo } from "@/lib/geoConvert";
import { ChatHeader } from "@/components/ChatHeader";
import { MessageList } from "@/components/MessageList";
import { ChatInput } from "@/components/ChatInput";
import { ExampleQueries } from "@/components/ExampleQueries";
import { DashboardGate } from "@/components/DashboardGate";

const GeoMap = dynamic(() => import("@/components/GeoMap").then((m) => m.GeoMap), {
  ssr: false,
  loading: () => (
    <div className="d-flex h-100 align-items-center justify-content-center text-muted small">
      Caricamento mappa…
    </div>
  ),
});

const LAYER_COLORS = [
  "#2563eb", "#dc2626", "#059669", "#d97706",
  "#7c3aed", "#0891b2", "#db2777", "#65a30d",
];

const SOURCE_LABEL: Record<string, string> = {
  ckan: "Catalogo CKAN",
  istat: "ISTAT",
  eurostat: "Eurostat",
  oecd: "OCSE",
  synth: "Sintesi",
};

type StreamEvent =
  | { event: "status"; source: string; phase: "start" | "end"; error?: string }
  | { event: "heartbeat"; in_flight: string[]; elapsed_ms: number }
  | { event: "result"; text: string; resources: Resource[] }
  | { event: "error"; message: string };

function statusLabel(ev: { source: string; phase: "start" | "end"; error?: string }): string {
  const label = SOURCE_LABEL[ev.source] ?? ev.source;
  if (ev.error) return `${label} ha riportato un errore — proseguo…`;
  if (ev.phase === "start") {
    return ev.source === "synth" ? "Sintesi finale in corso…" : `Interrogo ${label}…`;
  }
  return ev.source === "synth" ? "Sintesi completata" : `${label} ha risposto`;
}

function heartbeatLabel(ev: { in_flight: string[]; elapsed_ms: number }): string {
  const labels = ev.in_flight.map((s) => SOURCE_LABEL[s] ?? s);
  const human = labels.length > 1 ? labels.join(" + ") : labels[0] ?? "agente";
  const secs = Math.floor(ev.elapsed_ms / 1000);
  return `Ancora in lavorazione su ${human}… (${secs}s)`;
}

type MapPane = "chat" | "mappa"; // mobile-only tab

function EsploraInner() {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [prefill, setPrefill] = useState<string | undefined>(undefined);
  const [prefillKey, setPrefillKey] = useState(0);
  const [layers, setLayers] = useState<GeoLayer[]>([]);
  const [converting, setConverting] = useState(false);
  const [discardedCount, setDiscardedCount] = useState(0);
  const [unrenderableCount, setUnrenderableCount] = useState(0);
  const [focusLayerIds, setFocusLayerIds] = useState<string[] | undefined>(undefined);
  const [focusKey, setFocusKey] = useState(0);
  const [mobilePane, setMobilePane] = useState<MapPane>("chat");

  function pickExample(query: string) {
    setPrefill(query);
    setPrefillKey((n) => n + 1);
  }

  function toggleLayer(id: string) {
    setLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l)),
    );
  }

  function clearLayers() {
    setLayers([]);
    setDiscardedCount(0);
    setUnrenderableCount(0);
    setFocusLayerIds(undefined);
  }

  // Re-fit the map to the union of all visible mappable layers (manual button).
  function fitAll() {
    setFocusLayerIds(undefined);
    setFocusKey((n) => n + 1);
  }

  function resetChat() {
    setMessages([]);
    clearLayers();
  }

  async function _consumeStream(
    res: Response,
  ): Promise<{ final?: { text: string; resources: Resource[] }; streamError?: string }> {
    if (!res.ok || !res.body) return { streamError: `Errore HTTP ${res.status}` };
    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let final: { text: string; resources: Resource[] } | undefined;
    let streamError: string | undefined;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl: number;
      while ((nl = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line) continue;
        let ev: StreamEvent;
        try {
          ev = JSON.parse(line) as StreamEvent;
        } catch {
          continue;
        }
        if (ev.event === "status") setStatus(statusLabel(ev));
        else if (ev.event === "heartbeat") setStatus(heartbeatLabel(ev));
        else if (ev.event === "result") final = { text: ev.text, resources: ev.resources ?? [] };
        else if (ev.event === "error") streamError = ev.message;
      }
    }
    return { final, streamError };
  }

  async function send(query: string) {
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setLoading(true);
    setStatus(undefined);
    const t0 = performance.now();
    try {
      // /esplora is the chat+map experience: bias the orchestrator toward
      // geographic resources. This also triggers the synth-time geo_filter
      // that drops resources from a comune different from the one named in
      // the query (avoids "piste ciclabili Bologna" returning a CSV from
      // another region).
      const body: ChatRequest = { query, prefer_geo: true };
      const token = await getToken();
      const res = await apiFetch("/datasets/search/stream", {
        method: "POST",
        token,
        body: JSON.stringify(body),
      });
      const { final, streamError } = await _consumeStream(res);
      const durationMs = performance.now() - t0;
      if (streamError) {
        setMessages((prev) => [...prev, { role: "error", text: streamError }]);
        return;
      }
      if (!final) {
        setMessages((prev) => [
          ...prev,
          { role: "error", text: "Lo stream è terminato senza una risposta." },
        ]);
        return;
      }
      const resources = final.resources;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: final.text, resources, durationMs },
      ]);

      // Convert every resource; keep only the geographic ones for the map.
      // /datasets/proxy is auth-gated. Pass `getToken` (not the static token
      // from above) so each proxy call refreshes the Clerk JWT just-in-time:
      // an Ollama chat stream can take 60–90s and the token captured before
      // the stream would already be expired by the time we convert resources.
      setConverting(true);
      setStatus("Conversione dati geografici per la mappa…");
      try {
        const results = await Promise.all(
          resources.map(async (r) => ({ r, geo: await resourceToGeo(r, { getToken }) })),
        );
        let dropped = 0;
        let unrenderable = 0;
        const newIds: string[] = [];
        setLayers((prev) => {
          const next = [...prev];
          for (const { r, geo } of results) {
            if (geo && geo.status === "wms") {
              for (const wmsLayer of geo.layers) {
                const idx = next.length;
                const id = `${r.url || r.name}-${wmsLayer.name}-${idx}`;
                next.push({
                  id,
                  name: `${r.name || "WMS"} — ${wmsLayer.title || wmsLayer.name}`,
                  geojson: null,
                  wms: {
                    baseUrl: geo.baseUrl,
                    layerName: wmsLayer.name,
                    bbox: wmsLayer.bbox,
                  },
                  color: LAYER_COLORS[idx % LAYER_COLORS.length],
                  visible: true,
                });
                newIds.push(id);
              }
              continue;
            }
            if (geo && geo.status === "ok") {
              const idx = next.length;
              const id = `${r.url || r.name}-${idx}`;
              next.push({
                id,
                name: r.name || `Risorsa ${idx + 1}`,
                geojson: geo.geojson,
                color: LAYER_COLORS[idx % LAYER_COLORS.length],
                visible: true,
              });
              newIds.push(id);
              continue;
            }
            // Geographic but not renderable (GML, TopoJSON, fetch error,
            // bad GeoJSON). Don't add as a strikethrough panel entry — just
            // count it so we can surface the number in the toolbar note.
            if (geo && (geo.status === "unsupported" || geo.status === "error")) {
              unrenderable += 1;
              continue;
            }
            // resourceToGeo returned null → not a geographic resource at all
            // (CSV non-spatial, PDF, JSONL non-geo, …).
            dropped += 1;
          }
          return next;
        });
        setDiscardedCount((prev) => prev + dropped);
        setUnrenderableCount((prev) => prev + unrenderable);
        // Focus the map on the newly added layers so the user can see the
        // result of their latest question, while older layers stay available
        // via the panel and the "Vista globale" button.
        if (newIds.length > 0) {
          setFocusLayerIds(newIds);
          setFocusKey((n) => n + 1);
        }
      } finally {
        setConverting(false);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setMessages((prev) => [...prev, { role: "error", text: `Errore di rete: ${message}` }]);
    } finally {
      setLoading(false);
      setStatus(undefined);
    }
  }

  const geoCount = layers.length;

  // Chat pane (reused on desktop side-by-side AND on mobile when "chat" tab).
  const chatPane = (
    <div className="d-flex flex-column h-100 min-h-0 min-w-0">
      <ChatHeader
        onReset={resetChat}
        canReset={messages.length > 0 && !loading}
      />
      <MessageList
        messages={messages}
        loading={loading}
        statusMessage={status}
        emptyState={
          <div className="space-y-3">
            <p className="text-slate-500">
              Fai una domanda: l&apos;orchestrator interroga in parallelo i
              portali CKAN e le fonti statistiche ufficiali. Le risorse di
              tipo geografico (Shapefile, GeoJSON, KML, WMS) vengono
              automaticamente disegnate sulla mappa a destra; tutto il resto
              resta nella chat.
            </p>
            <ExampleQueries onPick={pickExample} disabled={loading} />
          </div>
        }
      />
      {messages.length > 0 ? (
        <div
          className="border-t border-slate-200 bg-slate-50 px-3 py-1.5 overflow-y-auto"
          style={{ maxHeight: "4.5rem", flexShrink: 0 }}
        >
          <ExampleQueries onPick={pickExample} disabled={loading} />
        </div>
      ) : null}
      <ChatInput
        onSubmit={send}
        loading={loading}
        prefill={prefill}
        prefillKey={prefillKey}
      />
    </div>
  );

  // Map pane.
  const mapPane = (
    <div className="d-flex flex-column h-100 min-h-0 position-relative">
      {/* Map toolbar: counter + actions. */}
      <div className="d-flex align-items-center justify-content-between px-3 py-2 border-bottom bg-white gap-2 flex-wrap">
        <div className="small">
          <strong>Mappa</strong>
          <span className="text-muted ms-2">
            {geoCount === 0
              ? "nessun layer"
              : `${geoCount} layer${geoCount === 1 ? "" : "s"} sulla mappa`}
            {unrenderableCount > 0
              ? ` · ${unrenderableCount} risors${unrenderableCount === 1 ? "a" : "e"} geografic${unrenderableCount === 1 ? "a" : "he"} non rappresentabil${unrenderableCount === 1 ? "e" : "i"}`
              : null}
            {discardedCount > 0
              ? ` · ${discardedCount} non geografic${discardedCount === 1 ? "a" : "he"}`
              : null}
          </span>
        </div>
        <div className="d-flex gap-2">
          <button
            type="button"
            className="btn btn-outline-secondary btn-sm"
            disabled={geoCount < 2 || converting}
            onClick={fitAll}
            title="Inquadra tutti i layer attivi"
          >
            Vista globale
          </button>
          <button
            type="button"
            className="btn btn-outline-secondary btn-sm"
            disabled={geoCount === 0 || converting}
            onClick={clearLayers}
          >
            Pulisci layer
          </button>
        </div>
      </div>

      {/* Leaflet map fills the remaining space. */}
      <div className="flex-grow-1 position-relative" style={{ minHeight: 360 }}>
        <GeoMap
          layers={layers}
          focusLayerIds={focusLayerIds}
          focusKey={focusKey}
        />

        {/* Floating layers panel — only mappable ones (no clutter). */}
        {geoCount > 0 ? (
          <div
            className="position-absolute"
            style={{
              top: 12,
              right: 12,
              maxHeight: "60%",
              width: 240,
              overflow: "auto",
              zIndex: 1000,
              backgroundColor: "rgba(255,255,255,0.95)",
              border: "1px solid #e2e8f0",
              borderRadius: 6,
              boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
              padding: 8,
            }}
          >
            <p
              className="mb-1 small text-uppercase fw-semibold text-muted"
              style={{ letterSpacing: "0.04em" }}
            >
              Layer ({geoCount})
            </p>
            <ul className="list-unstyled mb-0">
              {layers.map((l) => (
                <li
                  key={l.id}
                  className="d-flex align-items-center gap-2 small mb-1"
                >
                  <input
                    type="checkbox"
                    checked={l.visible}
                    onChange={() => toggleLayer(l.id)}
                  />
                  <span
                    className="d-inline-block flex-shrink-0"
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: 2,
                      backgroundColor: l.color,
                    }}
                  />
                  <span
                    className="text-truncate"
                    title={l.name}
                    style={{ color: "var(--color-text)" }}
                  >
                    {l.name}
                  </span>
                </li>
              ))}
            </ul>
            {converting ? (
              <p className="mt-1 small text-muted" style={{ fontSize: 10 }}>
                Conversione mappe…
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );

  return (
    <div className="d-flex flex-column flex-grow-1 min-h-0">
      {/* Mobile tab switcher (visible <lg). */}
      <div className="d-flex d-lg-none gap-1 border-bottom bg-light p-1">
        <button
          type="button"
          className={`btn btn-sm flex-grow-1 ${mobilePane === "chat" ? "btn-primary" : "btn-outline-secondary"}`}
          onClick={() => setMobilePane("chat")}
        >
          Chat
        </button>
        <button
          type="button"
          className={`btn btn-sm flex-grow-1 ${mobilePane === "mappa" ? "btn-primary" : "btn-outline-secondary"}`}
          onClick={() => setMobilePane("mappa")}
        >
          Mappa{geoCount > 0 ? ` (${geoCount})` : ""}
        </button>
      </div>

      {/* Desktop split (50/50) + mobile single-pane via tab. */}
      {/* `min-w-0` on both columns is essential: without it a wide child (a
          many-column table preview) refuses to shrink below its content width
          and steals the other column's 50% — the map collapses. With min-w-0
          the column keeps its basis and the table scrolls inside its own box. */}
      <div className="flex-grow-1 d-flex flex-column flex-lg-row min-h-0 min-w-0">
        <div
          className={`${mobilePane === "chat" ? "d-flex" : "d-none"} d-lg-flex flex-column min-h-0 min-w-0`}
          style={{ flex: "1 1 50%", borderRight: "1px solid var(--color-border)" }}
        >
          {chatPane}
        </div>
        <div
          className={`${mobilePane === "mappa" ? "d-flex" : "d-none"} d-lg-flex flex-column min-h-0 min-w-0`}
          style={{ flex: "1 1 50%" }}
        >
          {mapPane}
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <EsploraInner />
    </DashboardGate>
  );
}
