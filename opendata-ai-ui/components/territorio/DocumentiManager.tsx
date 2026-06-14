"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Documento } from "@/lib/types";

const STATO_BADGE: Record<string, { label: string; cls: string }> = {
  ingerito: { label: "Ingerito", cls: "bg-success" },
  in_ingest: { label: "In corso…", cls: "bg-secondary" },
  errore: { label: "Errore", cls: "bg-danger" },
};

/**
 * File manager dei documenti PA del comune (F2): carica un PDF/DOCX/TXT che
 * aggiorna la base di conoscenza (KG) e mostra cosa è stato ingerito. Caricare
 * o eliminare un documento invalida la cache delle analisi del comune.
 */
export function DocumentiManager({
  codComune,
  comuneNome,
}: {
  codComune: string;
  comuneNome?: string | null;
}) {
  const { getToken } = useAuth();
  const [docs, setDocs] = useState<Documento[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await apiFetch(
        `/territorio/documenti?cod_comune=${encodeURIComponent(codComune)}`,
        { token },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { documenti: Documento[] };
      setDocs(data.documenti ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [codComune, getToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const token = await getToken();
      const form = new FormData();
      form.append("cod_comune", codComune);
      form.append("file", file);
      const res = await apiFetch("/territorio/documenti", {
        method: "POST",
        token,
        body: form,
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}${detail ? ` — ${detail.slice(0, 200)}` : ""}`);
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function onDelete(id: number) {
    if (!confirm("Eliminare questo documento dalla base di conoscenza?")) return;
    setError(null);
    try {
      const token = await getToken();
      const res = await apiFetch(`/territorio/documenti/${id}`, { method: "DELETE", token });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div>
      <p className="small text-muted mb-2">
        Carica delibere, certificazioni o piani del comune
        {comuneNome ? ` di ${comuneNome}` : ""}: aggiornano la base di conoscenza
        e vengono usati come <em>evidenza documentale</em> nelle analisi (utile
        quando OpenCoesione non è aggiornato). Caricare o eliminare un documento
        rigenera l&apos;analisi al prossimo accesso.
      </p>

      <div className="d-flex align-items-center gap-2 mb-3">
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="form-control form-control-sm"
          style={{ maxWidth: 360 }}
          disabled={uploading}
          onChange={onUpload}
        />
        {uploading ? (
          <span className="small text-muted" role="status">
            Caricamento e ingest in corso…
          </span>
        ) : null}
      </div>

      {error ? (
        <div className="alert alert-warning py-2 small" role="alert">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="small text-muted">Carico l&apos;elenco…</p>
      ) : docs.length === 0 ? (
        <p className="small text-muted">Nessun documento caricato per questo comune.</p>
      ) : (
        <ul className="list-group">
          {docs.map((d) => {
            const badge = STATO_BADGE[d.stato] ?? { label: d.stato, cls: "bg-secondary" };
            return (
              <li
                key={d.id}
                className="list-group-item d-flex align-items-center justify-content-between gap-2"
              >
                <span className="text-truncate">
                  <span className={`badge ${badge.cls} me-2`}>{badge.label}</span>
                  <span className="fw-semibold">{d.filename}</span>
                  {d.pagine ? <span className="text-muted small ms-2">{d.pagine} pag.</span> : null}
                  {d.stato === "errore" && d.errore ? (
                    <span className="text-danger small ms-2" title={d.errore}>
                      (ingest non riuscito)
                    </span>
                  ) : null}
                </span>
                <button
                  type="button"
                  className="btn btn-outline-danger btn-sm flex-shrink-0"
                  onClick={() => onDelete(d.id)}
                >
                  Elimina
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
