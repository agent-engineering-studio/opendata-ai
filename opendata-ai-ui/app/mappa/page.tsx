"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useAuth } from "@/lib/auth";
import type { ChatMessage, ChatRequest, ChatResponse } from "@/lib/types";
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

export default function MapPage() {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [layers, setLayers] = useState<GeoLayer[]>([]);
  const [loading, setLoading] = useState(false);
  const [converting, setConverting] = useState(false);

  function toggleLayer(id: string) {
    setLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l)),
    );
  }

  async function send(query: string) {
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setLoading(true);
    const t0 = performance.now();
    try {
      const body: ChatRequest = { query };
      const token = await getToken();
      const res = await apiFetch("/datasets/search", {
        method: "POST",
        token,
        body: JSON.stringify(body),
      });
      const raw = await res.text();
      let parsed: ChatResponse | { error: string };
      try {
        parsed = JSON.parse(raw);
      } catch {
        parsed = { error: "Risposta non valida dal proxy" };
      }
      const durationMs = performance.now() - t0;
      if (!res.ok || "error" in parsed) {
        const errText = "error" in parsed ? parsed.error : `Errore HTTP ${res.status}`;
        setMessages((prev) => [...prev, { role: "error", text: errText }]);
      } else {
        const resources = parsed.resources ?? [];
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: parsed.text, resources, durationMs },
        ]);
        // Convert every geographic resource (GeoJSON/KML/GPX/SHP, fetched +
        // reprojected as needed) and accumulate them as map layers.
        setConverting(true);
        try {
          const results = await Promise.all(
            resources.map(async (r) => ({ r, geo: await resourceToGeo(r) })),
          );
          setLayers((prev) => {
            const next = [...prev];
            for (const { r, geo } of results) {
              // WMS: one entry per layer published by the GetCapabilities.
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
              const idx = next.length;
              const geojson = geo && geo.status === "ok" ? geo.geojson : null;
              const error =
                geo == null
                  ? `formato non geografico${r.format ? ` (${r.format})` : ""}`
                  : geo.status === "ok"
                    ? undefined
                    : geo.reason;
              next.push({
                id: `${r.url || r.name}-${idx}`,
                name: r.name || `Risorsa ${idx + 1}`,
                geojson,
                color: LAYER_COLORS[idx % LAYER_COLORS.length],
                visible: geojson != null,
                error,
              });
            }
            return next;
          });
        } finally {
          setConverting(false);
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setMessages((prev) => [...prev, { role: "error", text: `Errore di rete: ${message}` }]);
    } finally {
      setLoading(false);
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
            {loading ? (
              <div className="text-xs text-slate-400">L&apos;agente sta cercando…</div>
            ) : converting ? (
              <div className="text-xs text-slate-400">Conversione dati geografici per la mappa…</div>
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
