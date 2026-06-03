import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Note legali — OpenData AI",
};

// Placeholder. Replace with the actual terms before going to production.
export default function Page() {
  return (
    <article className="container py-5">
      <h1>Note legali</h1>
      <p className="lead">
        Condizioni d&apos;uso del servizio OpenData AI.
      </p>

      <section>
        <h2>Natura del servizio</h2>
        <p>
          OpenData AI aggrega in modo automatico dati pubblicati su portali
          CKAN italiani e fonti statistiche ufficiali (ISTAT, Eurostat,
          OCSE). Le informazioni restituite hanno valore informativo e non
          sostituiscono i dati ufficiali pubblicati dalle rispettive fonti.
        </p>
      </section>

      <section>
        <h2>Limitazione di responsabilità</h2>
        <p>
          Il servizio è fornito &ldquo;as is&rdquo; senza garanzie esplicite
          o implicite di accuratezza, completezza o adeguatezza a uno scopo
          specifico.
        </p>
      </section>

      <section>
        <h2>Diritti</h2>
        <p>
          Il software è rilasciato con licenza open source. I dataset
          ricalcano i termini di licenza delle rispettive fonti di origine
          (tipicamente CC BY o equivalenti).
        </p>
      </section>
    </article>
  );
}
