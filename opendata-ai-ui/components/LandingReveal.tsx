"use client";

import { useEffect } from "react";

/**
 * Micro-ottimizzazioni client della landing.
 *
 * L'effetto "reveal allo scroll" è stato RIMOSSO: nascondere le sezioni via
 * JS (classe `od-reveal--armed`) e rivelarle con IntersectionObserver si è
 * rotto più volte nei browser reali (sezioni che restavano invisibili → la
 * pagina sembrava troncata a metà). Il contenuto ora è sempre visibile,
 * senza dipendere da alcun JavaScript.
 *
 * Resta solo la parte che non può rompere nulla: le animazioni SVG infinite
 * dei diagrammi (`.od-flow*`, `.od-pulse`) girano solo quando il loro
 * contenitore [data-anim-scope] è in viewport (classe `od-anim-on`) — fuori
 * schermo restano in pausa e non appesantiscono lo scroll. Se l'observer
 * manca o fallisce, il fallback le attiva e basta.
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

    const animated = Array.from(
      document.querySelectorAll<HTMLElement>("[data-anim-scope]"),
    );
    if (animated.length === 0) return;

    if (!("IntersectionObserver" in window)) {
      animated.forEach((el) => el.classList.add("od-anim-on"));
      return;
    }
    const animIo = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          entry.target.classList.toggle("od-anim-on", entry.isIntersecting);
        });
      },
      { rootMargin: "80px 0px" },
    );
    animated.forEach((el) => animIo.observe(el));
    return () => animIo.disconnect();
  }, []);

  return null;
}
