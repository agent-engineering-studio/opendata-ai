"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Headers,
  Header,
  HeaderContent,
  HeaderBrand,
  HeaderLinkZone,
  HeaderRightZone,
  Nav,
  NavItem,
  NavLink,
} from "design-react-kit";
import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/clerk-react";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

const NAV = [
  { href: "/", label: "Chat" },
  { href: "/mappa", label: "Mappa" },
  { href: "/info", label: "Informazioni" },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <Headers sticky shadow>
      {/* Slim institutional bar: project descriptor + auth zone. */}
      <Header type="slim" theme="dark">
        <HeaderContent>
          <HeaderBrand href="/">OpenData AI — progetto sperimentale</HeaderBrand>
          <HeaderLinkZone>
            {hasClerk ? (
              <div className="it-header-slim-right-zone flex items-center gap-2">
                <SignedOut>
                  <SignInButton mode="modal">
                    <button className="btn btn-outline-primary btn-xs">
                      Accedi
                    </button>
                  </SignInButton>
                  <SignUpButton mode="modal">
                    <button className="btn btn-primary btn-xs">
                      Registrati
                    </button>
                  </SignUpButton>
                </SignedOut>
                <SignedIn>
                  <UserButton afterSignOutUrl="/" />
                </SignedIn>
              </div>
            ) : null}
          </HeaderLinkZone>
        </HeaderContent>
      </Header>

      {/* Main navbar: brand + page nav. */}
      <Header type="navbar" theme="light">
        <HeaderContent expand="lg" megamenu={false}>
          <HeaderBrand href="/" tag={Link}>
            <h2 className="mb-0">OpenData AI</h2>
            <p className="mb-0 text-sm">
              Open data CKAN + statistiche ufficiali (ISTAT, Eurostat, OCSE)
            </p>
          </HeaderBrand>
          <HeaderRightZone>
            <Nav navbar>
              {NAV.map((item) => {
                const active = pathname === item.href;
                return (
                  <NavItem key={item.href} active={active}>
                    <NavLink
                      tag={Link}
                      href={item.href}
                      active={active}
                      aria-current={active ? "page" : undefined}
                    >
                      <span>{item.label}</span>
                    </NavLink>
                  </NavItem>
                );
              })}
            </Nav>
          </HeaderRightZone>
        </HeaderContent>
      </Header>
    </Headers>
  );
}
