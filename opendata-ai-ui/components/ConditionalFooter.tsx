"use client";

import { usePathname } from "next/navigation";
import { SiteFooter } from "@/components/SiteFooter";

// Full-bleed app pages fill `main` exactly (chat/map, `h-100` roots, no scroll):
// there the footer must NOT be appended inside the scroll area, or it would
// add a scrollbar and push the app chrome. Everywhere else (landing, docs,
// territorio, maturità, legal…) the footer scrolls at the END of the page —
// which is the fix for the landing, where a sibling-of-`main` footer was
// pinned to the viewport bottom and overlapped the content.
const FULL_BLEED = ["/esplora", "/mappa"];

export function ConditionalFooter() {
  const pathname = usePathname() || "/";
  const hide = FULL_BLEED.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (hide) return null;
  return <SiteFooter />;
}
