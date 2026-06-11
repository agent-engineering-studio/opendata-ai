import Link from "next/link";

export type NextStep = {
  href: string;
  title: string;
  blurb: string;
  badge?: string;
};

/**
 * Grid of clickable cards used at the bottom of each docs page in place of
 * a plain bullet list. Looks like the docs index cards so navigation feels
 * uniform across the section.
 */
export function NextStepsCards({
  heading = "Prossimi passi",
  items,
}: {
  heading?: string;
  items: NextStep[];
}) {
  return (
    <section className="mt-5">
      <h2 className="mb-3">{heading}</h2>
      <div className="row g-3">
        {items.map((s) => (
          <div key={s.href} className="col-md-6">
            <Link
              href={s.href}
              className="card h-100 shadow-sm text-decoration-none text-reset"
            >
              <div className="card-body d-flex flex-column">
                <div className="d-flex align-items-center justify-content-between mb-2">
                  {s.badge ? (
                    <span className="badge bg-light text-dark">{s.badge}</span>
                  ) : (
                    <span />
                  )}
                  <span
                    aria-hidden="true"
                    className="text-primary fw-bold"
                    style={{ fontSize: "1.25rem", lineHeight: 1 }}
                  >
                    →
                  </span>
                </div>
                <h3 className="h6 mb-2">{s.title}</h3>
                <p className="small text-muted mb-0">{s.blurb}</p>
              </div>
            </Link>
          </div>
        ))}
      </div>
    </section>
  );
}
