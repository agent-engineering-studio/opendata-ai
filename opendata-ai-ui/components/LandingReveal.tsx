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
 * Due salvagenti contro la pagina "bloccata a metà":
 * - qualunque elemento ancora armato dopo 4s viene rivelato comunque
 *   (observer che non scatta ≠ contenuto perso);
 * - le animazioni SVG infinite dei diagrammi (`.od-flow*`, `.od-pulse`) girano
 *   solo quando il loro contenitore [data-anim-scope] è in viewport (classe
 *   `od-anim-on`): fuori schermo restano in pausa e non appesantiscono lo
 *   scroll.
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
    const reveal = (el: HTMLElement) => {
      const delay = Number(el.dataset.delay ?? "0");
      el.style.animationDelay = `${delay}ms`;
      el.classList.add("od-reveal--in");
    };

    let io: IntersectionObserver | undefined;
    let safety: number | undefined;
    if (nodes.length > 0) {
      // Arma gli elementi (nascondi) solo ora che il JS è attivo.
      nodes.forEach((el) => el.classList.add("od-reveal--armed"));

      if (!("IntersectionObserver" in window)) {
        // Nessun observer: rivela tutto subito così la pagina resta leggibile.
        nodes.forEach(reveal);
      } else {
        io = new IntersectionObserver(
          (entries) => {
            entries.forEach((entry) => {
              if (!entry.isIntersecting) return;
              const el = entry.target as HTMLElement;
              reveal(el);
              io?.unobserve(el);
            });
          },
          { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
        );
        nodes.forEach((el) => io!.observe(el));
        // Salvagente: nessun elemento resta invisibile per sempre. 2s: chi
        // scorre veloce non deve mai trovare sezioni vuote.
        safety = window.setTimeout(() => {
          nodes.forEach((el) => {
            if (!el.classList.contains("od-reveal--in")) reveal(el);
          });
        }, 2000);
      }
    }

    // Pausa/riprendi le animazioni infinite in base alla visibilità.
    const animated = Array.from(
      document.querySelectorAll<HTMLElement>("[data-anim-scope]"),
    );
    let animIo: IntersectionObserver | undefined;
    if (animated.length > 0 && "IntersectionObserver" in window) {
      animIo = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            entry.target.classList.toggle("od-anim-on", entry.isIntersecting);
          });
        },
        { rootMargin: "80px 0px" },
      );
      animated.forEach((el) => animIo!.observe(el));
    } else {
      animated.forEach((el) => el.classList.add("od-anim-on"));
    }

    return () => {
      io?.disconnect();
      animIo?.disconnect();
      if (safety !== undefined) window.clearTimeout(safety);
    };
  }, []);

  return null;
}
