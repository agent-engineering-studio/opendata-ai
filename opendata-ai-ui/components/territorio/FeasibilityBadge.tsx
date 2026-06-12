import type { LivelloFattibilita } from "@/lib/types";

/* Etichetta testuale sempre presente: il livello non è veicolato dal solo
 * colore (accessibilità). `da_verificare` è volutamente scuro, mai "verde". */
const STYLE: Record<LivelloFattibilita, { label: string; className: string }> = {
  alta: { label: "Fattibilità alta", className: "bg-success text-white" },
  media: { label: "Fattibilità media", className: "bg-warning text-white" },
  bassa: { label: "Fattibilità bassa", className: "bg-danger text-white" },
  da_verificare: { label: "Da verificare", className: "bg-dark text-white" },
};

export function FeasibilityBadge({ livello }: { livello: LivelloFattibilita }) {
  const s = STYLE[livello] ?? STYLE.da_verificare;
  return <span className={`badge ${s.className}`}>{s.label}</span>;
}
