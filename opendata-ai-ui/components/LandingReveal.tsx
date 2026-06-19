"use client";

import { useEffect } from "react";

/**
 * Reveal allo scroll per la landing (progressive enhancement).
 *
 * Gli elementi `[data-reveal]` partono VISIBILI nel markup statico: questo
 * componente li "arma" (li nasconde con `.od-reveal--armed`) solo a JS attivo,
 * poi via IntersectionObserver applica `.od-reveal--in` (fade + translateY 22px)
 * con uno stagger letto da `data-delay` (ms). Se l'utente preferisce meno
 * animazioni, il CSS neutralizza `--armed`/`--in` e tutto resta visibile.
 *
 * Rende `null`: opera direttamente sul DOM della pagina, così `app/page.tsx`
 * può restare un Server Component.
 */
export function LandingReveal() {
  useEffect(() => {
    const reduce =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;

    const nodes = Array.from(
      document.querySelectorAll<HTMLElement>("[data-reveal]"),
    );
    if (nodes.length === 0) return;

    // Arma gli elementi (nascondi) solo ora che il JS è attivo.
    nodes.forEach((el) => el.classList.add("od-reveal--armed"));

    if (!("IntersectionObserver" in window)) {
      // Nessun observer: rivela tutto subito così la pagina resta leggibile.
      nodes.forEach((el) => el.classList.add("od-reveal--in"));
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const el = entry.target as HTMLElement;
          const delay = Number(el.dataset.delay ?? "0");
          el.style.animationDelay = `${delay}ms`;
          el.classList.add("od-reveal--in");
          io.unobserve(el);
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
    );

    nodes.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return null;
}
