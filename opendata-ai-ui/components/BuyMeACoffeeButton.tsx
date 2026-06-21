"use client";

import { useEffect, useRef } from "react";

// Buy Me a Coffee widget. Lo script ufficiale (button.prod.min.js) legge i
// propri attributi data-* e inserisce il bottone subito dopo il tag <script>.
// Con `output: 'export'` non possiamo affidarci a next/script in <head>, perché
// il bottone deve materializzarsi qui nel DOM: iniettiamo lo script dentro un
// container con un effect lato client (slug f9t3zol).
export function BuyMeACoffeeButton() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || el.querySelector("script")) return; // evita doppie iniezioni (StrictMode)

    const script = document.createElement("script");
    script.src = "https://cdnjs.buymeacoffee.com/1.0.0/button.prod.min.js";
    script.setAttribute("data-name", "bmc-button");
    script.setAttribute("data-slug", "f9t3zol");
    script.setAttribute("data-color", "#FFDD00");
    script.setAttribute("data-emoji", "");
    script.setAttribute("data-font", "Cookie");
    script.setAttribute("data-text", "Support opendata-ai");
    script.setAttribute("data-outline-color", "#000000");
    script.setAttribute("data-font-color", "#000000");
    script.setAttribute("data-coffee-color", "#ffffff");
    el.appendChild(script);
  }, []);

  return (
    <div ref={ref} className="d-inline-flex align-items-center" aria-label="Buy Me a Coffee">
      {/* Fallback accessibile finché lo script non ha sostituito il contenuto. */}
      <noscript>
        <a href="https://www.buymeacoffee.com/f9t3zol" target="_blank" rel="noopener noreferrer">
          Support opendata-ai
        </a>
      </noscript>
    </div>
  );
}
