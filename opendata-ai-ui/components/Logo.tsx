/**
 * Marchio OpenData AI condiviso da header e footer.
 *
 * Rende la tile gradiente brand (raggio 12px) con il marchio bianco interno
 * (anello aperto + nodi-dati + scintilla `#7BE7C4` per contrasto) accanto al
 * wordmark "OpenData AI" in Space Grotesk 700, tracking -0.01em.
 *
 * - `size`   → lato della tile in px (min 32 da brand guideline). Default 40.
 * - `theme`  → "light" su sfondi chiari (ink wordmark), "dark" su sfondi scuri
 *              (wordmark bianco, "AI" teal chiaro).
 * - `showWordmark` → false per la sola tile.
 */
export function Logo({
  size = 40,
  theme = "light",
  showWordmark = true,
  className = "",
}: {
  size?: number;
  theme?: "light" | "dark";
  showWordmark?: boolean;
  className?: string;
}) {
  const inkColor = theme === "dark" ? "#ffffff" : "#0e2233";
  const aiColor = theme === "dark" ? "#5fd3d3" : "#1b6fe3";
  const glyph = Math.round(size * 0.575);

  return (
    <span
      className={`d-inline-flex align-items-center gap-2 ${className}`.trim()}
    >
      <span
        aria-hidden="true"
        className="d-inline-flex align-items-center justify-content-center flex-shrink-0"
        style={{
          width: size,
          height: size,
          borderRadius: 12,
          background: "var(--gradient-brand)",
          boxShadow: "0 6px 16px rgba(27,111,227,.32)",
        }}
      >
        {/* Marchio bianco (anello aperto + 3 nodi, scintilla AI chiara). */}
        <svg width={glyph} height={glyph} viewBox="0 0 48 48" fill="none">
          <circle
            cx="24"
            cy="24"
            r="15"
            stroke="#fff"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray="71 26"
            transform="rotate(-58 24 24)"
          />
          <circle cx="14.8" cy="30.6" r="2.8" fill="#fff" />
          <circle cx="23.6" cy="24.6" r="2.8" fill="#fff" />
          <circle cx="32.8" cy="17.4" r="3.7" fill="#7BE7C4" />
        </svg>
      </span>
      {showWordmark ? (
        <span
          className="font-display"
          style={{
            fontWeight: 700,
            fontSize: Math.round(size * 0.475),
            letterSpacing: "-0.01em",
            lineHeight: 1,
            color: inkColor,
            whiteSpace: "nowrap",
          }}
        >
          OpenData<span style={{ color: aiColor }}> AI</span>
        </span>
      ) : null}
    </span>
  );
}
