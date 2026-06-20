"use client";

import { useAuth as useClerkAuth } from "@clerk/clerk-react";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

type Props = {
  /** Stripe Payment Link; empty string falls back to `fallback`. */
  link: string;
  /** Used when `link` is empty (e.g. GitHub Sponsors). */
  fallback: string;
  prezzo: string;
  /** Filled vs outline button styling. */
  primary: boolean;
};

// Stripe Payment Links accept `client_reference_id` as a query param and echo
// it back on `checkout.session.completed` → the backend webhook binds the
// contributo to the signed-in Clerk user (robust mapping, no email guesswork).
// Signed-out users still pay; the webhook then falls back to matching the
// checkout email. See docs/sostieni.md → Roadmap tecnica del billing.
function withClientReference(link: string, userId: string | null | undefined): string {
  if (!userId || !link.includes("buy.stripe.com")) return link;
  const sep = link.includes("?") ? "&" : "?";
  return `${link}${sep}client_reference_id=${encodeURIComponent(userId)}`;
}

function Anchor({ href, prezzo, primary }: { href: string; prezzo: string; primary: boolean }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`btn ${primary ? "btn-primary" : "btn-outline-primary"} w-100`}
    >
      Sostieni con {prezzo} €/mese
    </a>
  );
}

function BoundButton({ link, fallback, prezzo, primary }: Props) {
  const { userId } = useClerkAuth();
  const href = link ? withClientReference(link, userId) : fallback;
  return <Anchor href={href} prezzo={prezzo} primary={primary} />;
}

/**
 * Contribution button that tags the Stripe Payment Link with the signed-in
 * user's Clerk id (`client_reference_id`) so the webhook can bind the
 * subscription to `opendata.users`. Mirrors `DashboardGate`'s keyless guard:
 * on a build without a Clerk key (local prerender / CI) there is no session to
 * read, so it renders the plain link.
 */
export function SostieniButton(props: Props) {
  if (!hasClerk) {
    return (
      <Anchor href={props.link || props.fallback} prezzo={props.prezzo} primary={props.primary} />
    );
  }
  return <BoundButton {...props} />;
}
