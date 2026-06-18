import type { LivelloFattibilita } from "@/lib/types";

/* Etichetta testuale sempre presente: il livello non è veicolato dal solo
 * colore (accessibilità). La fattibilità "da verificare" non è informativa e non
 * viene mostrata: vale il disclaimer generale che è una stima preliminare. */
const STYLE: Partial<Record<LivelloFattibilita, { label: string; className: string }>> = {
  alta: { label: "Fattibilità alta", className: "bg-success text-white" },
  media: { label: "Fattibilità media", className: "bg-warning text-white" },
  bassa: { label: "Fattibilità bassa", className: "bg-danger text-white" },
};

export function FeasibilityBadge({ livello }: { livello: LivelloFattibilita }) {
  const s = STYLE[livello];
  if (!s) return null;
  return <span className={`badge ${s.className}`}>{s.label}</span>;
}
