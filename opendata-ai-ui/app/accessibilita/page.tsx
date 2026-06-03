import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dichiarazione di accessibilità — OpenData AI",
};

// Placeholder content. Replace before any production deployment that
// targets a Pubblica Amministrazione audience: AgID requires the model
// declaration at https://form.agid.gov.it/.
export default function Page() {
  return (
    <article className="container py-5">
      <h1>Dichiarazione di accessibilità</h1>
      <p className="lead">
        Questa pagina raccoglie lo stato di conformità del sito alle linee
        guida AgID e agli standard WCAG 2.1 livello AA.
      </p>

      <section>
        <h2>Stato di conformità</h2>
        <p>
          Il sito è attualmente in fase di sviluppo. La dichiarazione
          ufficiale di accessibilità verrà pubblicata utilizzando il modello
          AgID prima del rilascio in produzione.
        </p>
      </section>

      <section>
        <h2>Contenuti non accessibili</h2>
        <p>
          Sezione da compilare al termine dell&apos;audit di accessibilità.
        </p>
      </section>

      <section>
        <h2>Modalità di invio segnalazioni</h2>
        <p>
          Per segnalare difficoltà di accesso a contenuti del sito, scrivere
          a{" "}
          <a href="mailto:accessibilita@example.org">
            accessibilita@example.org
          </a>
          . Risponderemo entro 30 giorni.
        </p>
      </section>
    </article>
  );
}
