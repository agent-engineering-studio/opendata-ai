import type { Metadata } from "next";
import Link from "next/link";

import { PageHero } from "@/components/PageHero";

export const metadata: Metadata = {
  title: "Il valore degli open data senza esporre i cittadini — OpenData AI",
  description:
    "Il patrimonio informativo della PA è un asset strategico, ma va valorizzato senza esporre i cittadini: dato personale vs dato aperto, anonimizzazione, pseudonimizzazione, k-anonymity, dati sintetici e Privacy Enhancing Technologies. Spunti e letture da Agenda Digitale.",
};

/*
 * Pagina editoriale long-form (pubblica, statica) sul rapporto tra valore degli
 * open data e tutela dei cittadini. Contenuto originale ispirato ai temi trattati
 * da Agenda Digitale (agendadigitale.eu); la sezione "Letture" rimanda agli
 * articoli/fonti senza riprodurne il testo. Stile e ancore allineati a
 * /guida-open-data (TOC + sezioni con scrollMarginTop + helper Riferimenti).
 */

type RefLink = { label: string; href: string };

function Riferimenti({ items }: { items: RefLink[] }) {
  return (
    <ul className="mt-2" style={{ fontSize: 14 }}>
      {items.map((r) => (
        <li key={r.href}>
          <a href={r.href} target="_blank" rel="noopener noreferrer">
            {r.label} →
          </a>
        </li>
      ))}
    </ul>
  );
}

const TOC: { id: string; label: string }[] = [
  { id: "asset", label: "Il dato pubblico come asset strategico" },
  { id: "tensione", label: "La tensione: aprire senza esporre" },
  { id: "personali", label: "Dato personale, dato aperto, dato aggregato" },
  { id: "tecniche", label: "Le tecniche di tutela" },
  { id: "principi", label: "I principi operativi" },
  { id: "opendata-ai", label: "Come OpenData AI applica questi principi" },
  { id: "letture", label: "Letture e riferimenti" },
];

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Cultura del dato"
        title="Il valore degli open data senza esporre i cittadini"
        lead={
          <>
            La Pubblica Amministrazione custodisce un patrimonio informativo enorme. Il dato è oggi uno
            degli asset più strategici per generare valore pubblico — ma la sfida non è tecnologica: è
            riuscire a <strong>valorizzarlo senza mai esporre le persone</strong> a cui, direttamente o
            indirettamente, si riferisce.
          </>
        }
      />
      <article className="container py-5" style={{ maxWidth: 880 }}>
        <p>
        Questa pagina raccoglie i concetti chiave che attraversano il dibattito sulla cittadinanza
        digitale — innovazione e intelligenza artificiale, interoperabilità dei sistemi e tutela della
        privacy — e li collega al modo in cui OpenData AI è progettato. È un contributo divulgativo:
        gli approfondimenti originali e le fonti autorevoli sono linkati in fondo.
      </p>

      <div
        className="alert alert-info"
        role="note"
        style={{ borderLeft: "4px solid var(--color-primary)" }}
      >
        <strong>Spunto di partenza.</strong> Questa lettura nasce dall&apos;articolo di Agenda Digitale
        &laquo;La PA ha un tesoro di dati: come usarli senza esporre i cittadini&raquo; (Leucio Maturo,
        giugno 2026). Lo trovi, insieme ad altre letture, nella sezione{" "}
        <a href="#letture" className="text-decoration-none">Letture e riferimenti</a>.
      </div>

      {/* Indice */}
      <nav
        aria-label="Indice della pagina"
        className="border rounded p-3 my-4"
        style={{ background: "var(--bs-light, #f8f9fa)" }}
      >
        <h2 className="h6 text-uppercase text-muted mb-2" style={{ letterSpacing: "0.06em" }}>
          In questa pagina
        </h2>
        <ol className="mb-0" style={{ fontSize: 14, columnGap: 32 }}>
          {TOC.map((t) => (
            <li key={t.id}>
              <a href={`#${t.id}`} className="text-decoration-none">
                {t.label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      {/* ── Asset ── */}
      <section id="asset" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Il dato pubblico come asset strategico</h2>
        <p>
          Anagrafe, tributi, mobilità, ambiente, urbanistica, servizi sociali: ogni ufficio produce e
          conserva dati. Aperti nel modo giusto, questi dati diventano un bene comune che alimenta
          trasparenza, ricerca, nuovi servizi e imprese. È la logica degli{" "}
          <strong>open data</strong>: informazione pubblica resa disponibile a tutti, in formato aperto
          e riutilizzabile, anche per fini commerciali.
        </p>
        <p>
          Proprio perché un open data è riutilizzabile <em>da chiunque, per qualsiasi scopo</em>, il
          valore e il rischio crescono insieme. Lo stesso dataset che permette a un&apos;associazione di
          mappare i servizi del territorio potrebbe, se mal preparato, permettere a un terzo di
          ricostruire informazioni su singole persone. Valorizzare il patrimonio informativo significa
          quindi tenere insieme tre esigenze: <strong>innovazione</strong> (anche con l&apos;AI),{" "}
          <strong>interoperabilità</strong> tra sistemi e <strong>tutela</strong> dei cittadini.
        </p>
      </section>

      {/* ── Tensione ── */}
      <section id="tensione" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>La tensione: aprire senza esporre</h2>
        <p>
          Il punto delicato non sono i dati palesemente personali (un nome, un codice fiscale): quelli
          si escludono o si oscurano facilmente. Il rischio vero è la{" "}
          <strong>re-identificazione</strong>: combinando più campi apparentemente innocui — età, CAP,
          professione, data di un evento — si può risalire a una persona, soprattutto in contesti piccoli
          come un comune. È il motivo per cui &laquo;togliere il nome&raquo; non basta quasi mai.
        </p>
        <p>
          La regola pratica che ne deriva è netta: <strong>meglio rinunciare a un dato che pubblicarne
          uno re-identificabile</strong>. Tra il valore marginale di un dettaglio in più e il rischio di
          esporre un cittadino, vince sempre la tutela. Da qui nasce tutta la cassetta degli attrezzi
          tecnica descritta più sotto.
        </p>
      </section>

      {/* ── Personali ── */}
      <section id="personali" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Dato personale, dato aperto, dato aggregato</h2>
        <p>
          Tre categorie aiutano a orientarsi. Un <strong>dato personale</strong> identifica una persona,
          direttamente o indirettamente, ed è protetto dal GDPR: non è materia da open data finché
          rimane tale. Un <strong>dato aperto</strong> è informazione pubblica, riutilizzabile e priva di
          riferimenti a persone identificabili. In mezzo c&apos;è il <strong>dato aggregato</strong>:
          numeri che descrivono insiemi (quanti residenti in una fascia d&apos;età, quanti permessi in un
          quartiere) senza che dal singolo numero si risalga al singolo individuo.
        </p>
        <p>
          Il lavoro di apertura consiste proprio nel portare un&apos;informazione dalla prima categoria
          alla seconda — di norma passando per l&apos;aggregazione — con garanzie verificabili. È un
          passaggio che coinvolge sia profili tecnici (come trasformare il dato) sia profili giuridici
          (qual è la base normativa, qual è la finalità), e che richiede il coinvolgimento del{" "}
          <strong>DPO</strong> nei casi dubbi.
        </p>
      </section>

      {/* ── Tecniche ── */}
      <section id="tecniche" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Le tecniche di tutela</h2>
        <p>
          Esiste una famiglia di approcci — le <strong>Privacy Enhancing Technologies (PET)</strong> —
          pensate per estrarre valore dai dati riducendo al minimo l&apos;esposizione delle persone. Le
          più ricorrenti nel contesto della PA:
        </p>
        <ul>
          <li>
            <strong>Anonimizzazione.</strong> Trasformazione irreversibile che rende impossibile (entro
            limiti ragionevoli) risalire all&apos;individuo. Un dato veramente anonimo esce dal perimetro
            del GDPR — ma l&apos;anonimato va dimostrato, non dichiarato.
          </li>
          <li>
            <strong>Pseudonimizzazione.</strong> Sostituzione degli identificatori con codici, mantenendo
            separata la chiave di corrispondenza. Riduce il rischio ma <em>non</em> rende anonimo il dato:
            resta dato personale a tutti gli effetti.
          </li>
          <li>
            <strong>K-anonymity.</strong> Garantire che ogni combinazione di attributi pubblicati sia
            condivisa da almeno <em>k</em> individui, così che nessun record sia isolabile. È una difesa
            diretta contro la re-identificazione per incrocio di campi.
          </li>
          <li>
            <strong>Dati sintetici.</strong> Dataset generati artificialmente che riproducono le
            proprietà statistiche di quelli reali senza contenere record di persone vere. Utili per test,
            sviluppo e addestramento di modelli senza toccare dati personali.
          </li>
        </ul>
        <p>
          Nessuna tecnica è una bacchetta magica: la scelta dipende dall&apos;uso previsto e dal livello
          di rischio. Spesso si combinano (ad esempio aggregazione + k-anonymity) e vanno riviste nel
          tempo, perché ciò che è anonimo oggi può diventare re-identificabile domani con nuovi dataset in
          circolazione.
        </p>
      </section>

      {/* ── Principi ── */}
      <section id="principi" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>I principi operativi</h2>
        <p>
          Le tecniche poggiano su alcuni principi del GDPR che ogni ente dovrebbe applicare prima di
          pubblicare:
        </p>
        <ul>
          <li>
            <strong>Limitazione della finalità.</strong> I dati si trattano per scopi determinati ed
            espliciti. L&apos;apertura va valutata rispetto alla finalità per cui i dati erano stati
            raccolti.
          </li>
          <li>
            <strong>Minimizzazione.</strong> Si pubblica solo ciò che serve allo scopo, non &laquo;tutto
            quello che c&apos;è&raquo;. Ogni campo in più è rischio in più.
          </li>
          <li>
            <strong>Privacy by design e by default.</strong> La protezione si progetta a monte, nei
            processi di pubblicazione, non si rincorre a valle.
          </li>
          <li>
            <strong>Valutazione d&apos;impatto (DPIA).</strong> Quando il trattamento può presentare un
            rischio elevato, va condotta una valutazione formale, coinvolgendo il DPO.
          </li>
        </ul>
        <p>
          Sono gli stessi principi che la{" "}
          <Link href="/guida-open-data" className="text-decoration-none">guida all&apos;apertura dei dati
          in un Comune</Link> traduce in passi operativi (bonifica, verifica privacy con il DPO, qualità)
          prima della pubblicazione su un catalogo.
        </p>
      </section>

      {/* ── OpenData AI ── */}
      <section id="opendata-ai" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Come OpenData AI applica questi principi</h2>
        <p>
          OpenData AI nasce su un presupposto coerente con tutto quanto sopra: <strong>lavora solo su
          dati già pubblici e già aperti</strong>, provenienti da fonti ufficiali (ISTAT, OpenCoesione,
          OpenStreetMap, cataloghi CKAN come dati.gov.it). Non raccoglie, non carica e non rielabora dati
          personali dei cittadini: trasforma open data in risposte utili, non viceversa.
        </p>
        <ul>
          <li>
            <strong>Nessun nuovo trattamento di dati personali.</strong> Le analisi partono da dataset
            aggregati e da metadati pubblici; non c&apos;è re-identificazione né arricchimento di profili
            individuali.
          </li>
          <li>
            <strong>Ogni numero è tracciabile alla fonte.</strong> Ogni risposta cita la risorsa
            ufficiale da cui proviene il dato — niente numeri inventati, così l&apos;informazione resta
            verificabile dal cittadino.
          </li>
          <li>
            <strong>&laquo;Dato insufficiente&raquo; invece di punteggi falsi.</strong> Sotto la soglia
            minima di dati disponibili l&apos;analisi lo dichiara, anziché produrre punteggi fuorvianti.
          </li>
        </ul>
        <p>
          Per i dettagli sul trattamento dei dati degli utenti del servizio (account, cronologia) fai
          riferimento alla <Link href="/privacy" className="text-decoration-none">informativa privacy</Link>{" "}
          e alle <Link href="/note-legali" className="text-decoration-none">note legali</Link>.
        </p>
      </section>

      {/* ── Letture ── */}
      <section id="letture" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Letture e riferimenti</h2>

        <h3 className="h5 mt-4">Approfondimenti su Agenda Digitale</h3>
        <Riferimenti
          items={[
            {
              label:
                "La PA ha un tesoro di dati: come usarli senza esporre i cittadini (L. Maturo)",
              href: "https://www.agendadigitale.eu/cittadinanza-digitale/la-pa-ha-un-tesoro-di-dati-come-usarli-senza-esporre-i-cittadini/",
            },
            {
              label: "Agenda Digitale — sezione Cittadinanza digitale",
              href: "https://www.agendadigitale.eu/cittadinanza-digitale/",
            },
            {
              label: "Agenda Digitale — tutti gli articoli sugli open data",
              href: "https://www.agendadigitale.eu/tag/open-data/",
            },
          ]}
        />

        <h3 className="h5 mt-4">Tutela dei dati personali</h3>
        <Riferimenti
          items={[
            {
              label: "Garante per la protezione dei dati personali",
              href: "https://www.garanteprivacy.it",
            },
            {
              label: "European Data Protection Board (EDPB) — linee guida",
              href: "https://www.edpb.europa.eu/our-work-tools/general-guidance/guidelines-recommendations-best-practices_it",
            },
            {
              label: "Regolamento (UE) 2016/679 — GDPR (testo)",
              href: "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679",
            },
          ]}
        />

        <h3 className="h5 mt-4">Open data nella PA</h3>
        <Riferimenti
          items={[
            {
              label: "AgID — Open Data",
              href: "https://www.agid.gov.it/it/ambiti-intervento/open-data",
            },
            {
              label: "dati.gov.it — il catalogo nazionale",
              href: "https://www.dati.gov.it",
            },
            {
              label: "OpenData AI — guida all'apertura dei dati in un Comune",
              href: "/guida-open-data",
            },
          ]}
        />
      </section>

      <p className="text-muted small mt-5">
        Questa pagina ha carattere informativo e divulgativo; non sostituisce gli atti ufficiali né la
        consulenza legale. I contenuti sono originali e ispirati ai temi trattati dalle fonti citate, di
        cui non riproducono il testo. Fare sempre riferimento ai testi normativi e ai provvedimenti del
        Garante vigenti.
      </p>
      </article>
    </>
  );
}
