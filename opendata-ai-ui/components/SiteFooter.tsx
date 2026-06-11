import Link from "next/link";

const GITHUB_URL = "https://github.com/agent-engineering-studio/opendata-ai";
const AE_URL = "https://www.agentengineering.it";
const ANTHROPIC_URL = "https://www.anthropic.com";

function AnthropicMark({ className = "h-4 w-auto" }: { className?: string }) {
  // Anthropic "A" mark (same path used by Wamply BrandFooter).
  return (
    <svg viewBox="0 0 46 32" className={className} aria-hidden="true" fill="none">
      <path
        d="M32.73 0H27.2l12.8 32h5.53L32.73 0zM12.8 0L0 32h5.67l2.63-6.74h13.41L24.33 32H30L17.2 0h-4.4zm-1.96 20.37L15 10.2l4.16 10.17H10.84z"
        fill="#D4A27F"
      />
    </svg>
  );
}

function GitHubIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="currentColor">
      <path d="M12 .5C5.65.5.5 5.65.5 12.02c0 5.1 3.29 9.42 7.86 10.94.57.1.78-.25.78-.55v-2.07c-3.2.69-3.87-1.36-3.87-1.36-.52-1.34-1.28-1.7-1.28-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.78 1.19 1.78 1.19 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.47.11-3.06 0 0 .97-.31 3.18 1.18.92-.26 1.91-.39 2.9-.4.99.01 1.98.14 2.9.4 2.21-1.49 3.18-1.18 3.18-1.18.63 1.59.23 2.77.11 3.06.74.81 1.19 1.83 1.19 3.09 0 4.42-2.69 5.4-5.25 5.68.41.36.78 1.05.78 2.12v3.14c0 .31.21.66.79.55 4.57-1.53 7.85-5.84 7.85-10.94C23.5 5.65 18.35.5 12 .5z" />
    </svg>
  );
}

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="bg-primary-900 text-white" role="contentinfo">
      {/* Main footer band: brand + tagline on the left, tech credit on the right. */}
      <div className="container py-4">
        <div className="row align-items-center g-4">
          <div className="col-md-6">
            <Link href="/" className="text-decoration-none text-white">
              <h2 className="h4 mb-1">OpenData AI</h2>
              <p className="small mb-0" style={{ opacity: 0.75 }}>
                Open data CKAN + statistiche ufficiali (ISTAT, Eurostat, OCSE)
              </p>
            </Link>
          </div>

          <div className="col-md-6">
            <div className="d-flex flex-wrap align-items-center justify-content-md-end gap-3">
              <a
                href={ANTHROPIC_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="d-inline-flex align-items-center gap-2 text-decoration-none"
                style={{ color: "rgba(255,255,255,0.75)" }}
                title="Powered by Anthropic Claude"
              >
                <AnthropicMark className="h-4 w-auto" />
                <span className="small">Powered by Claude</span>
              </a>

              <span
                aria-hidden="true"
                style={{
                  width: 1,
                  height: 16,
                  backgroundColor: "rgba(255,255,255,0.2)",
                }}
              />

              <a
                href={AE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="d-inline-flex align-items-center gap-2 text-decoration-none"
                style={{ color: "rgba(255,255,255,0.75)" }}
                title="Designed by Agent Engineering Studio"
              >
                <span
                  className="text-uppercase"
                  style={{ fontSize: 10, letterSpacing: "0.12em" }}
                >
                  Designed by
                </span>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/agent-engineering-logo.png"
                  alt="Agent Engineering Studio"
                  style={{ height: 28, width: "auto" }}
                />
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Small prints band — divider + bottom row with legal/docs links + GitHub icon. */}
      <div
        className="py-3"
        style={{ borderTop: "1px solid rgba(255,255,255,0.12)" }}
      >
        <div className="container">
          <div className="d-flex flex-wrap align-items-center justify-content-between gap-3">
            <ul
              className="list-inline mb-0 d-flex flex-wrap gap-3 small"
              style={{ opacity: 0.8 }}
            >
              <li className="list-inline-item m-0">
                © {year} OpenData AI
              </li>
              <li className="list-inline-item m-0">
                <Link href="/docs" className="text-white text-decoration-none">
                  Documentazione
                </Link>
              </li>
              <li className="list-inline-item m-0">
                <Link
                  href="/note-legali"
                  className="text-white text-decoration-none"
                >
                  Note legali
                </Link>
              </li>
              <li className="list-inline-item m-0">
                <Link
                  href="/privacy"
                  className="text-white text-decoration-none"
                >
                  Privacy
                </Link>
              </li>
            </ul>

            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="d-inline-flex align-items-center gap-2 text-decoration-none text-white"
              aria-label="Repository GitHub opendata-ai"
              style={{ opacity: 0.85 }}
            >
              <GitHubIcon className="h-4 w-4" />
              <span className="small">GitHub</span>
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
