import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy policy — OpenData AI",
};

// Placeholder. Replace with the actual GDPR-compliant text before any
// production deployment that processes personal data.
export default function Page() {
  return (
    <article className="container py-5">
      <h1>Privacy policy</h1>
      <p className="lead">
        Informativa ai sensi degli articoli 13 e 14 del Regolamento UE
        2016/679 (GDPR).
      </p>

      <section>
        <h2>Dati raccolti</h2>
        <p>
          Per l&apos;accesso al servizio è richiesta autenticazione tramite
          Clerk. Vengono trattati l&apos;indirizzo email e il nome
          dell&apos;utente. La cronologia delle ricerche viene conservata
          per personalizzare l&apos;esperienza.
        </p>
      </section>

      <section>
        <h2>Finalità del trattamento</h2>
        <p>
          I dati vengono utilizzati esclusivamente per: erogazione del
          servizio, gestione dell&apos;account utente e personalizzazione
          delle risposte dell&apos;agente.
        </p>
      </section>

      <section>
        <h2>Diritti dell&apos;interessato</h2>
        <p>
          L&apos;utente può in qualsiasi momento richiedere accesso,
          rettifica, cancellazione o limitazione del trattamento dei propri
          dati scrivendo a{" "}
          <a href="mailto:privacy@example.org">privacy@example.org</a>.
        </p>
      </section>
    </article>
  );
}
