"use client";

import { useEffect, useState } from "react";
import type JSZip from "jszip";
import { CsvTablePreview } from "./CsvTablePreview";
import { ResourcePreview, isPreviewable } from "./ResourcePreview";
import { GeoResourceMap } from "./GeoResourceMap";

type ZipEntry = {
  name: string;
  ext: string;
  size: number;
  display: string; // basename without leading dirs
};

function entryExt(name: string): string {
  const base = name.split("/").pop() || name;
  const i = base.lastIndexOf(".");
  return i >= 0 ? base.slice(i + 1).toLowerCase() : "";
}

function isJunk(name: string): boolean {
  return (
    name.startsWith("__MACOSX/") ||
    name.endsWith("/.DS_Store") ||
    name.endsWith("/Thumbs.db") ||
    name.endsWith(".DS_Store")
  );
}

function humanSize(b: number): string {
  if (!b) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

const TEXT_EXTS = new Set(["csv", "json", "geojson", "kml", "gpx", "txt", "xml", "rdf", "md"]);
const MAP_EXTS = new Set(["geojson", "kml", "gpx"]);

type State =
  | { kind: "loading" }
  | { kind: "error"; msg: string }
  | {
      kind: "ok";
      zip: JSZip;
      entries: ZipEntry[];
      shortcut: "shapefile" | "kmz" | null;
    };

export function ZipPreview({ url, name }: { url?: string; name?: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!url) {
        if (!cancelled) setState({ kind: "error", msg: "ZIP senza URL scaricabile" });
        return;
      }
      try {
        const resp = await fetch(`/api/proxy?url=${encodeURIComponent(url)}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const buf = await resp.arrayBuffer();
        const JSZip = (await import("jszip")).default;
        const zip = await JSZip.loadAsync(buf);
        const entries: ZipEntry[] = Object.entries(zip.files)
          .filter(([n, f]) => !f.dir && !isJunk(n))
          .map(([n, f]) => {
            // jszip exposes the uncompressed size via the (private) _data field.
            const size =
              (f as unknown as { _data?: { uncompressedSize?: number } })._data
                ?.uncompressedSize ?? 0;
            return { name: n, ext: entryExt(n), size, display: n.split("/").pop() || n };
          })
          .sort((a, b) => a.name.localeCompare(b.name));
        const exts = new Set(entries.map((e) => e.ext));
        const shortcut: "shapefile" | "kmz" | null =
          exts.has("shp") && exts.has("dbf")
            ? "shapefile"
            : entries.some((e) => e.ext === "kml")
              ? "kmz"
              : null;
        if (!cancelled) setState({ kind: "ok", zip, entries, shortcut });
      } catch (e) {
        if (!cancelled)
          setState({ kind: "error", msg: e instanceof Error ? e.message : String(e) });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [url]);

  if (state.kind === "loading")
    return <div className="text-xs text-slate-500">Apertura archivio…</div>;
  if (state.kind === "error")
    return (
      <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
        Impossibile aprire il ZIP: {state.msg}.
      </div>
    );

  const { zip, entries, shortcut } = state;

  if (shortcut === "shapefile") {
    return (
      <div className="space-y-2">
        <p className="text-xs text-slate-500">
          Archivio shapefile riconosciuto ({entries.length} file) — disegno sulla mappa.
        </p>
        <GeoResourceMap content={null} url={url} format="SHP" />
        <EntryList zip={zip} entries={entries} title={name} />
      </div>
    );
  }
  if (shortcut === "kmz") {
    const kml = entries.find((e) => e.ext === "kml");
    if (kml) return <KmzShortcut zip={zip} kmlName={kml.name} entries={entries} title={name} />;
  }

  return <EntryList zip={zip} entries={entries} title={name} />;
}

function KmzShortcut({
  zip,
  kmlName,
  entries,
  title,
}: {
  zip: JSZip;
  kmlName: string;
  entries: ZipEntry[];
  title?: string;
}) {
  const [kml, setKml] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    zip
      .file(kmlName)
      ?.async("string")
      .then((t) => {
        if (!cancelled) setKml(t);
      });
    return () => {
      cancelled = true;
    };
  }, [zip, kmlName]);
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">KMZ riconosciuto — disegno sulla mappa.</p>
      {kml ? (
        <GeoResourceMap content={kml} format="KML" />
      ) : (
        <div className="text-xs text-slate-500">Estrazione KML…</div>
      )}
      <EntryList zip={zip} entries={entries} title={title} />
    </div>
  );
}

function EntryList({
  zip,
  entries,
  title,
}: {
  zip: JSZip;
  entries: ZipEntry[];
  title?: string;
}) {
  if (entries.length === 0)
    return <p className="text-xs text-slate-500">Archivio vuoto.</p>;
  return (
    <div className="space-y-1">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">
        Contenuto archivio{title ? ` — ${title}` : ""} ({entries.length} file)
      </p>
      <ul className="space-y-1">
        {entries.map((e) => (
          <li key={e.name}>
            <EntryRow zip={zip} entry={e} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function EntryRow({ zip, entry }: { zip: JSZip; entry: ZipEntry }) {
  const [open, setOpen] = useState(false);
  const canPreview =
    TEXT_EXTS.has(entry.ext) || entry.ext === "pdf";

  return (
    <div className="rounded border border-slate-200">
      <div className="flex items-center gap-2 px-2 py-1">
        <span className="inline-flex min-w-[3.5rem] justify-center rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700">
          {entry.ext ? entry.ext.toUpperCase() : "—"}
        </span>
        <span className="flex-1 truncate text-xs text-slate-700" title={entry.name}>
          {entry.display}
        </span>
        <span className="shrink-0 text-[11px] text-slate-400">{humanSize(entry.size)}</span>
        {canPreview ? (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="shrink-0 text-[11px] font-medium text-slate-600 hover:text-slate-900"
          >
            {open ? "▾ Nascondi" : "▸ Anteprima"}
          </button>
        ) : (
          <DownloadButton zip={zip} entry={entry} />
        )}
      </div>
      {open && canPreview ? (
        <div className="border-t border-slate-100 px-2 py-2">
          <EntryPreview zip={zip} entry={entry} />
        </div>
      ) : null}
    </div>
  );
}

function EntryPreview({ zip, entry }: { zip: JSZip; entry: ZipEntry }) {
  const [text, setText] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const isText = TEXT_EXTS.has(entry.ext);
  const isPdf = entry.ext === "pdf";

  useEffect(() => {
    let cancelled = false;
    let createdUrl: string | null = null;
    const f = zip.file(entry.name);
    if (!f) {
      setErr("voce non trovata");
      return;
    }
    (async () => {
      try {
        if (isText) {
          const t = await f.async("string");
          if (!cancelled) setText(t);
        } else if (isPdf) {
          const blob = await f.async("blob");
          createdUrl = URL.createObjectURL(
            new Blob([blob], { type: "application/pdf" }),
          );
          if (!cancelled) setBlobUrl(createdUrl);
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [zip, entry.name, isText, isPdf]);

  if (err) return <div className="text-xs text-red-700">Errore: {err}.</div>;

  if (isPdf) {
    if (!blobUrl) return <div className="text-xs text-slate-500">Estrazione PDF…</div>;
    return (
      <iframe
        src={blobUrl}
        title={entry.name}
        className="h-96 w-full rounded border border-slate-200"
      />
    );
  }

  if (!isText) return null;
  if (text == null) return <div className="text-xs text-slate-500">Lettura…</div>;

  const fmt = entry.ext.toUpperCase();
  // Geographic text → reuse the map component (handles GeoJSON/KML/GPX).
  if (MAP_EXTS.has(entry.ext)) {
    return <GeoResourceMap content={text} format={fmt} />;
  }
  // CSV → tabular preview.
  if (entry.ext === "csv") {
    return <CsvTablePreview content={text} url="" />;
  }
  // JSON/TXT/XML/RDF/MD → generic textual preview when supported.
  if (isPreviewable(fmt, text, "")) {
    return <ResourcePreview format={fmt} content={text} url="" />;
  }
  // Last resort: show as plain text.
  return (
    <pre className="max-h-96 overflow-auto rounded bg-slate-50 px-2 py-1 text-[11px] text-slate-700">
      {text.slice(0, 20_000)}
      {text.length > 20_000 ? "\n…[troncato]" : ""}
    </pre>
  );
}

function DownloadButton({ zip, entry }: { zip: JSZip; entry: ZipEntry }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          const blob = await zip.file(entry.name)!.async("blob");
          const u = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = u;
          a.download = entry.display;
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(() => URL.revokeObjectURL(u), 1000);
        } finally {
          setBusy(false);
        }
      }}
      className="shrink-0 text-[11px] font-medium text-slate-600 hover:text-slate-900 disabled:opacity-50"
    >
      {busy ? "…" : "↓ Scarica"}
    </button>
  );
}

