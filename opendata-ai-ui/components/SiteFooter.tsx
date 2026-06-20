import Link from "next/link";
import { Logo } from "@/components/Logo";

const GITHUB_URL = "https://github.com/agent-engineering-studio/opendata-ai";
const AE_URL = "https://www.agentengineering.it";
const ANTHROPIC_URL = "https://www.anthropic.com";
const OLLAMA_URL = "https://ollama.com";

const LINK_COLOR = "#8C9BA8";
const HEADING_COLOR = "#5B6B7B";

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

function OllamaMark({ className = "h-4 w-auto" }: { className?: string }) {
  // Minimal monochrome llama glyph for the "powered by" credit (footer scale).
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="currentColor">
      <path d="M7.1 2.2c-1 0-1.7.9-1.9 2-.2.9-.1 1.9.2 2.8-1 1-1.6 2.4-1.6 4.1 0 1.3.4 2.4 1 3.4-.5.8-.8 1.8-.8 2.9 0 .9.2 1.7.5 2.4.2.4.6.6 1 .5.4-.1.6-.5.5-.9-.2-.6-.3-1.2-.3-1.9 0-.5.1-1 .2-1.4.5.4 1.1.7 1.7.9-.1.4-.2.9-.2 1.4 0 .6.1 1.2.4 1.7.2.4.6.5 1 .4.4-.2.5-.6.4-1-.1-.3-.2-.6-.2-1 0-.3 0-.5.1-.7.5.1 1.1.1 1.6.1s1.1 0 1.6-.1c.1.2.1.4.1.7 0 .4-.1.7-.2 1-.1.4 0 .8.4 1 .4.1.8 0 1-.4.3-.5.4-1.1.4-1.7 0-.5-.1-1-.2-1.4.6-.2 1.2-.5 1.7-.9.1.4.2.9.2 1.4 0 .7-.1 1.3-.3 1.9-.1.4.1.8.5.9.4.1.8-.1 1-.5.3-.7.5-1.5.5-2.4 0-1.1-.3-2.1-.8-2.9.6-1 1-2.1 1-3.4 0-1.7-.6-3.1-1.6-4.1.3-.9.4-1.9.2-2.8-.2-1.1-.9-2-1.9-2-.9 0-1.6.7-2 1.7-.9-.3-1.8-.3-2.7 0-.4-1-1.1-1.7-2-1.7zm1.4 7.1c.6 0 1 .6 1 1.3s-.4 1.3-1 1.3-1-.6-1-1.3.4-1.3 1-1.3zm7 0c.6 0 1 .6 1 1.3s-.4 1.3-1 1.3-1-.6-1-1.3.4-1.3 1-1.3zM12 13c.8 0 1.5.4 1.5.9 0 .3-.3.6-.7.8.2.1.4.4.4.6 0 .5-.5.8-1.2.8s-1.2-.3-1.2-.8c0-.2.2-.5.4-.6-.4-.2-.7-.5-.7-.8 0-.5.7-.9 1.5-.9z" />
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

function FooterCol({
  title,
  links,
}: {
  title: string;
  links: { href: string; label: string; external?: boolean }[];
}) {
  return (
    <div>
      <div
        className="text-uppercase mb-3"
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.12em",
          color: HEADING_COLOR,
        }}
      >
        {title}
      </div>
      <ul className="list-unstyled d-flex flex-column gap-2 mb-0">
        {links.map((l) => (
          <li key={l.href + l.label}>
            {l.external ? (
              <a
                href={l.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-decoration-none"
                style={{ color: LINK_COLOR, fontSize: 14 }}
              >
                {l.label}
              </a>
            ) : (
              <Link
                href={l.href}
                className="text-decoration-none"
                style={{ color: LINK_COLOR, fontSize: 14 }}
              >
                {l.label}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer
      role="contentinfo"
      style={{ background: "#0A1826", color: LINK_COLOR }}
    >
      <div className="container" style={{ paddingTop: 54, paddingBottom: 40 }}>
        <div className="d-flex flex-wrap justify-content-between gap-4">
          {/* Brand + tagline */}
          <div style={{ maxWidth: 320 }}>
            <Link href="/" className="text-decoration-none d-inline-block mb-3">
              <Logo size={36} theme="dark" />
            </Link>
            <p
              className="mb-0"
              style={{ fontSize: 13.5, lineHeight: 1.6, color: "#7E8B97" }}
            >
              Dalla maturità degli open data al valore per il territorio.
              Progetto open source · licenza MIT.
            </p>
          </div>

          {/* Link columns */}
          <div className="d-flex flex-wrap" style={{ gap: 56 }}>
            <FooterCol
              title="Prodotto"
              links={[
                { href: "/#percorso", label: "Il percorso" },
                { href: "/#come", label: "Come funziona" },
                { href: "/#perchi", label: "Per chi è" },
              ]}
            />
            <FooterCol
              title="Sviluppatori"
              links={[
                { href: "/docs", label: "Documentazione" },
                { href: "/usecases", label: "Casi d'uso" },
                { href: "/sostieni", label: "Sostieni il progetto" },
              ]}
            />
            <FooterCol
              title="Legale"
              links={[
                { href: "/privacy", label: "Privacy" },
                { href: "/note-legali", label: "Note legali" },
                {
                  href: GITHUB_URL,
                  label: "Licenza MIT",
                  external: true,
                },
              ]}
            />
          </div>
        </div>

        {/* Bottom band: sources + credits */}
        <div
          className="d-flex flex-wrap align-items-center justify-content-between gap-3"
          style={{
            marginTop: 36,
            paddingTop: 22,
            borderTop: "1px solid rgba(255,255,255,0.08)",
            fontSize: 12.5,
            color: HEADING_COLOR,
          }}
        >
          <span style={{ lineHeight: 1.5 }}>
            © {year} OpenData AI · Dati da fonti ufficiali ISTAT, OpenCoesione,
            OpenStreetMap e portali CKAN.
          </span>

          <div className="d-flex flex-wrap align-items-center gap-3">
            <span
              className="d-inline-flex align-items-center gap-2"
              style={{ color: LINK_COLOR }}
              title="Modelli: Anthropic Claude e Ollama (cloud o locale)"
            >
              <a
                href={ANTHROPIC_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="d-inline-flex align-items-center text-decoration-none"
                style={{ color: LINK_COLOR }}
                aria-label="Anthropic Claude"
              >
                <AnthropicMark className="h-4 w-auto" />
              </a>
              <a
                href={OLLAMA_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="d-inline-flex align-items-center text-decoration-none"
                style={{ color: LINK_COLOR }}
                aria-label="Ollama"
              >
                <OllamaMark className="h-4 w-auto" />
              </a>
              <span style={{ fontSize: 12.5 }}>Powered by Claude · Ollama</span>
            </span>
            <span
              aria-hidden="true"
              style={{ width: 1, height: 14, background: "rgba(255,255,255,0.16)" }}
            />
            <a
              href={AE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="d-inline-flex align-items-center gap-2 text-decoration-none"
              style={{ color: LINK_COLOR }}
              title="Designed by Agent Engineering Studio"
            >
              <span
                className="text-uppercase"
                style={{ fontSize: 10, letterSpacing: "0.12em" }}
              >
                Designed by AES
              </span>
            </a>
            <span
              aria-hidden="true"
              style={{ width: 1, height: 14, background: "rgba(255,255,255,0.16)" }}
            />
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="d-inline-flex align-items-center gap-2 text-decoration-none"
              style={{ color: LINK_COLOR }}
              aria-label="Repository GitHub opendata-ai"
            >
              <GitHubIcon className="h-4 w-4" />
              <span style={{ fontSize: 12.5 }}>GitHub</span>
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
