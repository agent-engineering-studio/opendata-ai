/**
 * Il disclaimer è obbligatorio (garantito dai guardrail del backend) e va
 * mostrato in evidenza: distingue l'analisi su dati pubblici dal materiale
 * elettorale.
 */
export function DisclaimerBanner({ text }: { text: string }) {
  return (
    <div
      className="alert alert-info mb-4"
      role="note"
      style={{ borderLeft: "4px solid var(--color-primary)" }}
    >
      <strong>Nota di metodo.</strong> {text}
    </div>
  );
}
