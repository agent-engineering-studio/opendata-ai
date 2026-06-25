import type { ReactNode } from "react";

/*
 * Hero band riusato dalle pagine "documento" (privacy, note-legali,
 * guida-open-data, approfondimenti) per allinearle alle pagine landing
 * (roadmap, sostieni). Stesse classi Bootstrap dell'hero di /roadmap e
 * /sostieni — bg-primary-900 + container py-5 — così il look è identico.
 */
export function PageHero({
  eyebrow,
  title,
  lead,
}: {
  eyebrow?: string;
  title: string;
  lead?: ReactNode;
}) {
  return (
    <section className="bg-primary-900 text-white">
      <div className="container py-5">
        <div className="col-lg-9">
          {eyebrow ? (
            <p
              className="mb-2 text-uppercase small fw-semibold"
              style={{ letterSpacing: "0.1em", opacity: 0.8 }}
            >
              {eyebrow}
            </p>
          ) : null}
          <h1 className="display-5 fw-bold mb-3">{title}</h1>
          {lead ? (
            <p className="lead mb-0" style={{ opacity: 0.95 }}>
              {lead}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
