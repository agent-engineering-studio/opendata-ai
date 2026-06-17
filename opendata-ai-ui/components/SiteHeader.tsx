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

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

const PUBLIC_NAV = [
  { href: "/", label: "Home" },
  { href: "/docs", label: "Documentazione" },
] as const;

const AUTH_NAV = [
  { href: "/esplora", label: "Esplora" },
  { href: "/territorio", label: "Territorio" },
  { href: "/scorecard", label: "Scorecard" },
  { href: "/valore", label: "Valore" },
  { href: "/territorio-report", label: "Report comune" },
  { href: "/usecases", label: "Casi d'uso" },
  { href: "/sito-civico", label: "Sito civico" },
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

function NavLinks({ pathname }: { pathname: string }) {
  const items = (
    <>
      {PUBLIC_NAV.map((item) => (
        <NavItemLink key={item.href} item={item} pathname={pathname} />
      ))}
      {hasClerk ? (
        <SignedIn>
          {AUTH_NAV.map((item) => (
            <NavItemLink key={item.href} item={item} pathname={pathname} />
          ))}
        </SignedIn>
      ) : (
        AUTH_NAV.map((item) => (
          <NavItemLink key={item.href} item={item} pathname={pathname} />
        ))
      )}
    </>
  );
  return (
    <ul className="d-none d-lg-flex list-unstyled mb-0 align-items-center gap-1">
      {items}
    </ul>
  );
}

function NavItemLink({
  item,
  pathname,
}: {
  item: { href: string; label: string };
  pathname: string;
}) {
  const active = pathname === item.href;
  return (
    <li>
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
        className="d-inline-block px-3 py-2 text-decoration-none rounded"
        style={{
          color: active ? "var(--color-primary)" : "var(--color-text)",
          fontWeight: active ? 600 : 500,
          fontSize: 14,
          backgroundColor: active ? "var(--color-primary-100)" : "transparent",
        }}
      >
        {item.label}
      </Link>
    </li>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <header className="sticky-top shadow-sm" style={{ zIndex: 1030 }}>
      {/* Slim institutional bar — only the project descriptor. */}
      <div
        className="text-white"
        style={{ backgroundColor: "var(--color-primary-900)" }}
      >
        <div className="container py-1">
          <span className="small" style={{ opacity: 0.85 }}>
            OpenData AI — progetto sperimentale
          </span>
        </div>
      </div>

      {/* Main navbar — 3 zones: brand | centered nav | avatar/auth */}
      <div className="bg-white border-bottom">
        <div className="container">
          <div className="d-flex align-items-center py-3 gap-3">
            {/* Brand (left) */}
            <Link
              href="/"
              className="text-decoration-none text-reset d-flex align-items-center gap-2"
              style={{ minWidth: 0 }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/logo-mark.svg"
                alt=""
                width={40}
                height={40}
                className="flex-shrink-0"
              />
              <span style={{ minWidth: 0 }}>
                <h1 className="h4 mb-0">OpenData AI</h1>
                <p className="small text-muted mb-0 d-none d-md-block">
                  Open data CKAN + statistiche ufficiali
                </p>
              </span>
            </Link>

            {/* Nav (centered) — pushed to center via flex-grow on both sides */}
            <nav className="flex-grow-1 d-flex justify-content-center" aria-label="Navigazione principale">
              <NavLinks pathname={pathname} />
            </nav>

            {/* Auth zone (right) */}
            <div className="d-flex align-items-center gap-2 flex-shrink-0">
              {hasClerk ? (
                <>
                  <SignedOut>
                    <SignInButton mode="modal">
                      <button type="button" className="btn btn-outline-primary btn-sm">
                        Accedi
                      </button>
                    </SignInButton>
                    <SignUpButton mode="modal">
                      <button type="button" className="btn btn-primary btn-sm">
                        Registrati
                      </button>
                    </SignUpButton>
                  </SignedOut>
                  <SignedIn>
                    <UserButton afterSignOutUrl="/">
                      <UserButton.MenuItems>
                        <UserButton.Action
                          label="API keys (in arrivo)"
                          labelIcon={<KeyIcon />}
                          onClick={() => router.push("/account/api-keys")}
                        />
                      </UserButton.MenuItems>
                    </UserButton>
                  </SignedIn>
                </>
              ) : null}
            </div>
          </div>

          {/* Mobile nav — visible on <lg. Wraps under the brand row. */}
          <nav
            className="d-flex d-lg-none flex-wrap gap-2 pb-3"
            aria-label="Navigazione mobile"
          >
            {PUBLIC_NAV.map((item) => (
              <NavItemLink key={item.href} item={item} pathname={pathname} />
            ))}
            {hasClerk ? (
              <SignedIn>
                {AUTH_NAV.map((item) => (
                  <NavItemLink key={item.href} item={item} pathname={pathname} />
                ))}
              </SignedIn>
            ) : (
              AUTH_NAV.map((item) => (
                <NavItemLink key={item.href} item={item} pathname={pathname} />
              ))
            )}
          </nav>
        </div>
      </div>
    </header>
  );
}
