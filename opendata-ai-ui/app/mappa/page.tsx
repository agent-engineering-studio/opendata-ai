"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useAuth } from "@/lib/auth";
import type { ChatMessage, ChatRequest, Resource } from "@/lib/types";
import type { GeoLayer } from "@/components/GeoMap";
import { apiFetch } from "@/lib/api";
import { resourceToGeo } from "@/lib/geoConvert";
import { ChatInput } from "@/components/ChatInput";
import { AssistantMarkdown } from "@/components/AssistantMarkdown";

// Leaflet touches `window`; load the map only on the client.
const GeoMap = dynamic(() => import("@/components/GeoMap").then((m) => m.GeoMap), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-slate-400">
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

export default function MapPage() {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [layers, setLayers] = useState<GeoLayer[]>([]);
  const [loading, setLoading] = useState(false);
  const [converting, setConverting] = useState(false);
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [discardedCount, setDiscardedCount] = useState(0);

  function toggleLayer(id: string) {
    setLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l)),
    );
  }

  async function _consumeStream(
    res: Response,
  ): Promise<{ final?: { text: string; resources: Resource[] }; streamError?: string }> {
    if (!res.ok || !res.body) {
      return { streamError: `Errore HTTP ${res.status}` };
    }
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
      // prefer_geo biases the backend toward GeoJSON/Shapefile/KML/WMS resources.
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
      // Convert every resource and keep ONLY the geographic ones (GeoJSON / WMS).
      // Tabular CSV/JSON resources are intentionally hidden from the map view:
      // they're already in the assistant text on the right pane.
      setConverting(true);
      setStatus("Conversione dati geografici per la mappa…");
      try {
        const results = await Promise.all(
          resources.map(async (r) => ({ r, geo: await resourceToGeo(r) })),
        );
        let dropped = 0;
        setLayers((prev) => {
          const next = [...prev];
          for (const { r, geo } of results) {
            if (geo && geo.status === "wms") {
              for (const wmsLayer of geo.layers) {
                const idx = next.length;
                next.push({
                  id: `${r.url || r.name}-${wmsLayer.name}-${idx}`,
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
              }
              continue;
            }
            if (geo && geo.status === "ok") {
              const idx = next.length;
              next.push({
                id: `${r.url || r.name}-${idx}`,
                name: r.name || `Risorsa ${idx + 1}`,
                geojson: geo.geojson,
                color: LAYER_COLORS[idx % LAYER_COLORS.length],
                visible: true,
              });
              continue;
            }
            // Non-geographic resource: drop it from the map layers panel.
            dropped += 1;
          }
          return next;
        });
        setDiscardedCount((prev) => prev + dropped);
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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-[var(--color-border)] bg-white px-4 py-2">
        <p className="text-xs text-[var(--color-text-muted)]">
          Chiedi dati geografici: compaiono come layer sulla mappa OpenStreetMap.
        </p>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* Map */}
        <div className="relative min-h-0 flex-1">
          <GeoMap layers={layers} />
          {geoCount > 0 ? (
            <div className="absolute right-3 top-3 z-[1000] max-h-[60%] w-60 overflow-auto rounded-md border border-slate-200 bg-white/95 p-2 shadow">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Layer ({geoCount})
              </p>
              <ul className="space-y-1">
                {layers.map((l) => {
                  const mappable = l.geojson != null || l.wms != null;
                  return (
                    <li key={l.id} className="flex items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={l.visible}
                        disabled={!mappable}
                        onChange={() => toggleLayer(l.id)}
                      />
                      <span
                        className="inline-block h-3 w-3 shrink-0 rounded-sm"
                        style={{ backgroundColor: mappable ? l.color : "#cbd5e1" }}
                      />
                      <span
                        className={`truncate ${mappable ? "text-slate-700" : "text-slate-400 line-through"}`}
                        title={mappable ? l.name : `${l.name} — ${l.error ?? "non mappabile"}`}
                      >
                        {l.name}
                      </span>
                    </li>
                  );
                })}
              </ul>
              {converting ? (
                <p className="mt-1 text-[10px] text-slate-400">Conversione mappe…</p>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* Chat sidebar */}
        <aside className="flex w-96 min-w-0 flex-col border-l border-slate-200 bg-slate-50">
          <div className="flex-1 space-y-3 overflow-auto p-3">
            {messages.length === 0 ? (
              <p className="text-sm text-slate-500">
                Esempi: &laquo;confini della Toscana&raquo;, &laquo;comuni della
                provincia di Bologna&raquo;, &laquo;aree naturali protette in
                Lombardia&raquo;. I risultati GeoJSON appaiono sulla mappa.
              </p>
            ) : (
              messages.map((m, i) => (
                <div
                  key={i}
                  className={`rounded-md px-3 py-2 text-sm ${
                    m.role === "user"
                      ? "bg-blue-600 text-white"
                      : m.role === "error"
                        ? "border border-red-200 bg-red-50 text-red-700"
                        : "border border-slate-200 bg-white text-slate-800"
                  }`}
                >
                  {m.role === "assistant" ? (
                    <AssistantMarkdown text={m.text} />
                  ) : (
                    m.text
                  )}
                </div>
              ))
            )}
            {loading || converting ? (
              <div className="animate-pulse text-xs text-slate-500">
                {status ?? "L’agente sta cercando…"}
              </div>
            ) : discardedCount > 0 ? (
              <div className="text-xs text-slate-400">
                {discardedCount} risors{discardedCount === 1 ? "a" : "e"} non geografic
                {discardedCount === 1 ? "a" : "he"} omess
                {discardedCount === 1 ? "a" : "e"} dalla mappa (sono nel testo).
              </div>
            ) : null}
          </div>
          <div className="border-t border-slate-200 p-3">
            <ChatInput onSubmit={send} loading={loading} />
          </div>
        </aside>
      </div>
    </div>
  );
}
