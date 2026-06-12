import type { Resource } from "@/lib/types";

/** Elenco completo delle fonti raccolte dagli specialisti (in coda alla scheda). */
export function SourcesList({ citazioni }: { citazioni: Resource[] }) {
  if (citazioni.length === 0) return null;
  return (
    <details className="mt-4">
      <summary className="fw-semibold" style={{ cursor: "pointer" }}>
        Tutte le fonti utilizzate ({citazioni.length})
      </summary>
      <ul className="small mt-2 mb-0">
        {citazioni.map((r, i) => (
          <li key={i} className="mb-1">
            {r.source ? <span className="text-uppercase fw-semibold">[{r.source}] </span> : null}
            {r.name}{" "}
            <a
              href={r.url}
              target="_blank"
              rel="noreferrer"
              className="text-decoration-underline"
              style={{ wordBreak: "break-all" }}
            >
              {r.url}
            </a>
          </li>
        ))}
      </ul>
    </details>
  );
}
