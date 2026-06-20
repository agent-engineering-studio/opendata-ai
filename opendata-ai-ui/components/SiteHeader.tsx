"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/clerk-react";
import { Logo } from "@/components/Logo";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

// Nav marketing: anchor verso le sezioni della landing. Prefisso "/" così
// funzionano anche da pagine interne (vanno alla home e scrollano).
const LANDING_NAV = [
  { href: "/#percorso", label: "Il percorso" },
  { href: "/#come", label: "Come funziona" },
  { href: "/#perchi", label: "Per chi" },
  { href: "/#sviluppatori", label: "Sviluppatori" },
  { href: "/docs", label: "Documentazione" },
  { href: "/sostieni", label: "Sostieni" },
] as const;

// Nav prodotto: mostrata agli utenti autenticati al posto degli anchor.
const APP_NAV = [
  { href: "/esplora", label: "Esplora" },
  { href: "/territorio", label: "Territorio" },
  { href: "/maturita", label: "Maturità" },
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

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();

  // Marketing anchors per visitatori; nav prodotto per utenti loggati.
  const renderNav = (extraClass: string) => (
    <>
      {hasClerk ? (
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
            {hasClerk ? (
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
                  <UserButton afterSignOutUrl="/">
                    <UserButton.MenuItems>
                      <UserButton.Action
                        label="La tua chiave LLM"
                        labelIcon={<KeyIcon />}
                        onClick={() => router.push("/account/llm-key")}
                      />
                      <UserButton.Action
                        label="API keys (in arrivo)"
                        labelIcon={<KeyIcon />}
                        onClick={() => router.push("/account/api-keys")}
                      />
                    </UserButton.MenuItems>
                  </UserButton>
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
      </div>
    </header>
  );
}
