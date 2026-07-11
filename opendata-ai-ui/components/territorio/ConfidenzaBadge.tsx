import type { ConfidenzaSuolo } from "@/lib/types";

/* Badge di confidenza del record di riconciliazione del suolo (§4.5). Etichetta
 * testuale sempre presente: il livello non è veicolato dal solo colore
 * (accessibilità), come per FeasibilityBadge. */
const STYLE: Record<ConfidenzaSuolo, { label: string; className: string }> = {
  Alta: { label: "Confidenza alta", className: "bg-success text-white" },
  Media: { label: "Confidenza media", className: "bg-warning text-white" },
  Bassa: { label: "Confidenza bassa", className: "bg-danger text-white" },
};

export function ConfidenzaBadge({ livello }: { livello: ConfidenzaSuolo }) {
  const s = STYLE[livello] ?? STYLE.Bassa;
  return <span className={`badge ${s.className}`}>{s.label}</span>;
}
