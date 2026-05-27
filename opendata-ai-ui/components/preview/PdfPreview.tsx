"use client";

import { useEffect, useState } from "react";

/**
 * Renders a PDF inline. Embedding the source URL directly fails on most open-data
 * portals (X-Frame-Options / CSP block cross-origin framing, plus http→https mixed
 * content) → blank iframe. Instead we fetch the file through our same-origin
 * `/api/proxy`, turn it into a blob: URL, and frame that. Falls back to an
 * "Apri" link on error (e.g. file too large for the proxy cap).
 */
export function PdfPreview({ url }: { url: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setSrc(null);
    setError(null);

    (async () => {
      try {
        const resp = await fetch(`/api/proxy?url=${encodeURIComponent(url)}`, {
          signal: controller.signal,
        });
        if (!resp.ok) {
          let detail = `HTTP ${resp.status}`;
          try {
            const j = (await resp.json()) as { error?: string };
            if (j.error) detail = j.error;
          } catch {
            /* keep default */
          }
          setError(detail);
          return;
        }
        const buf = await resp.blob();
        const blob =
          buf.type === "application/pdf"
            ? buf
            : new Blob([buf], { type: "application/pdf" });
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof Error ? err.message : String(err));
      }
    })();

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  if (error) {
    return (
      <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
        Anteprima PDF non disponibile: {error}.{" "}
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium underline"
        >
          Apri il PDF
        </a>
      </div>
    );
  }

  if (!src) {
    return <div className="text-xs text-slate-500">Caricamento PDF…</div>;
  }

  return (
    <div className="overflow-hidden rounded border border-slate-200">
      <iframe
        src={src}
        title="Anteprima PDF"
        className="block h-[28rem] w-full bg-slate-50"
      />
    </div>
  );
}
