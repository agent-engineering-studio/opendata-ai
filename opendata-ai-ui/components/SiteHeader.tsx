"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  authConfigured,
  useAuth,
} from "@/lib/auth";
import { Logo } from "@/components/Logo";
import { RegioneTitle } from "@/components/RegioneTitle";

const hasAuth = authConfigured;

// Nav marketing: anchor verso le sezioni della landing. Prefisso "/" così
// funzionano anche da pagine interne (vanno alla home e scrollano).
const LANDING_NAV = [
  { href: "/#percorso", label: "Il percorso" },
  { href: "/#come", label: "Come funziona" },
  { href: "/#perchi", label: "Per chi" },
  { href: "/#sviluppatori", label: "Sviluppatori" },
  { href: "/#approfondimenti", label: "Cultura del dato" },
  { href: "/docs", label: "Documentazione" },
  { href: "/roadmap", label: "Roadmap" },
  { href: "/sostieni", label: "Sostieni" },
] as const;

// Nav prodotto: mostrata agli utenti autenticati al posto degli anchor.
const APP_NAV = [
  { href: "/regione", label: "Regione" },
  { href: "/esplora", label: "Esplora" },
  { href: "/territorio", label: "Territorio" },
  { href: "/idee", label: "Idea Lab" },
  { href: "/maturita", label: "Maturità" },
  { href: "/qualita", label: "Qualità" },
  { href: "/copilota", label: "Copilota" },
] as const;

function KeyIcon() {
  // Small key glyph used as the API keys menu icon in the Clerk UserButton.
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="15" r="4" />
      <path d="m21.2 7.7-8.8 8.8" />
      <path d="m15.6 7.7 5.6 0 0 5.6" />
      <path d="m11 12 2-2 5 5 2-2" />
    </svg>
  );
}

function NavLink({
  item,
  pathname,
}: {
  item: { href: string; label: string };
  pathname: string;
}) {
  // Active state only for product links (anchors non hanno path proprio).
  const active = pathname === item.href;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className="text-decoration-none px-2 py-1 rounded"
      style={{
        color: active ? "var(--color-primary)" : "var(--color-text-muted)",
        fontWeight: 600,
        fontSize: 14.5,
      }}
    >
      {item.label}
    </Link>
  );
}

// Signed-in avatar + dropdown (replaces Clerk's <UserButton>). Controlled menu,
// no Bootstrap JS dependency: account shortcuts + sign out.
function UserMenu() {
  const router = useRouter();
  const { user, role, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const initial = (user?.name || user?.email || "?").trim().charAt(0).toUpperCase();

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <div className="position-relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Menu utente"
        className="btn rounded-circle d-flex align-items-center justify-content-center"
        style={{
          width: 40,
          height: 40,
          background: "var(--color-primary)",
          color: "#fff",
          fontWeight: 700,
        }}
      >
        {initial}
      </button>
      {open && (
        <>
          <div
            className="position-fixed top-0 start-0 w-100 h-100"
            style={{ zIndex: 1040 }}
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            role="menu"
            className="position-absolute end-0 mt-2 bg-white border rounded shadow-sm py-1"
            style={{ zIndex: 1050, minWidth: 220 }}
          >
            {user?.email && (
              <div className="px-3 py-2 text-muted small border-bottom text-truncate">
                {user.email}
              </div>
            )}
            <button type="button" role="menuitem" className="dropdown-item d-flex align-items-center gap-2" onClick={() => go("/account/llm-key")}>
              <KeyIcon /> La tua chiave LLM
            </button>
            <button type="button" role="menuitem" className="dropdown-item d-flex align-items-center gap-2" onClick={() => go("/account/api-keys")}>
              <KeyIcon /> API keys (in arrivo)
            </button>
            {role === "admin" && (
              <>
                <div className="dropdown-divider" />
                <button type="button" role="menuitem" className="dropdown-item d-flex align-items-center gap-2" onClick={() => go("/admin")}>
                  <span aria-hidden="true">🛡️</span> Amministrazione
                </button>
              </>
            )}
            <div className="dropdown-divider" />
            <button type="button" role="menuitem" className="dropdown-item text-danger" onClick={() => signOut()}>
              Esci
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export function SiteHeader() {
  const pathname = usePathname();

  // Marketing anchors per visitatori; nav prodotto per utenti loggati.
  const renderNav = (extraClass: string) => (
    <>
      {hasAuth ? (
        <>
          <SignedOut>
            <nav
              className={extraClass}
              aria-label="Navigazione sezioni"
            >
              {LANDING_NAV.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} />
              ))}
            </nav>
          </SignedOut>
          <SignedIn>
            <nav className={extraClass} aria-label="Navigazione prodotto">
              {APP_NAV.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} />
              ))}
            </nav>
          </SignedIn>
        </>
      ) : (
        <nav className={extraClass} aria-label="Navigazione sezioni">
          {LANDING_NAV.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
        </nav>
      )}
    </>
  );

  return (
    <header
      className="sticky-top"
      style={{
        zIndex: 1030,
        background: "rgba(255,255,255,0.85)",
        backdropFilter: "saturate(180%) blur(14px)",
        WebkitBackdropFilter: "saturate(180%) blur(14px)",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <div className="container">
        <div
          className="d-flex align-items-center justify-content-between gap-3"
          style={{ height: 70 }}
        >
          {/* Brand (left) */}
          <Link
            href="/"
            className="text-decoration-none flex-shrink-0"
            aria-label="OpenData AI — home"
          >
            <Logo size={40} theme="light" />
          </Link>

          {/* Nav (center, ≥lg) */}
          {renderNav(
            "d-none d-lg-flex align-items-center gap-4 flex-grow-1 justify-content-center",
          )}

          {/* Auth / CTA (right) */}
          <div className="d-flex align-items-center gap-2 flex-shrink-0">
            {hasAuth ? (
              <>
                <SignedOut>
                  <SignInButton mode="modal">
                    <button
                      type="button"
                      className="btn btn-link text-decoration-none d-none d-sm-inline"
                      style={{
                        color: "var(--color-text-muted)",
                        fontWeight: 600,
                        fontSize: 14.5,
                      }}
                    >
                      Accedi
                    </button>
                  </SignInButton>
                  <SignUpButton mode="modal">
                    <button
                      type="button"
                      className="btn-brand"
                      style={{ padding: "10px 20px", fontSize: 14.5 }}
                    >
                      Prova ora
                    </button>
                  </SignUpButton>
                </SignedOut>
                <SignedIn>
                  <UserMenu />
                </SignedIn>
              </>
            ) : (
              <Link
                href="/login"
                className="btn-brand"
                style={{ padding: "10px 20px", fontSize: 14.5 }}
              >
                Prova ora
              </Link>
            )}
          </div>
        </div>

        {/* Nav mobile (<lg): wrappa sotto la barra brand. */}
        {renderNav(
          "d-flex d-lg-none flex-wrap align-items-center gap-3 pb-3",
        )}

        {/* Titolo esplicativo: quale regione stiamo monitorando (globale). */}
        <RegioneTitle />
      </div>
    </header>
  );
}
