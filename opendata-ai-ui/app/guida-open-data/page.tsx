import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Come avviare una politica di open data in un Comune — OpenData AI",
  description:
    "Guida passo passo per un Comune che parte da zero nell'apertura dei dati: governance, censimento, scelta dei dataset, privacy, formati e licenze, metadati DCAT-AP_IT, pubblicazione su CKAN e federazione con dati.gov.it.",
};

/*
 * Guida operativa long-form (pubblica, statica) per avviare una politica di open
 * data in un Comune. È la pagina di destinazione del disclaimer mostrato quando un
 * ente ha punteggio di maturità 0 / "dato insufficiente", e delle deep-link "Guida →"
 * agganciate alle singole raccomandazioni della scorecard. Le ancore di sezione
 * (#step-1 … #step-8, #quadro, #checklist, #riferimenti) sono mappate in
 * lib/maturityGuidance.ts: NON rinominarle senza aggiornare quella mappa.
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
  { id: "quadro", label: "Il quadro di riferimento in due minuti" },
  { id: "step-1", label: "1 — Governance e volontà politica" },
  { id: "step-2", label: "2 — Censire il patrimonio informativo" },
  { id: "step-3", label: "3 — Scegliere e prioritizzare i dataset" },
  { id: "step-4", label: "4 — Bonifica, privacy e qualità" },
  { id: "step-5", label: "5 — Formati aperti e licenza" },
  { id: "step-6", label: "6 — Metadati DCAT-AP_IT" },
  { id: "step-7", label: "7 — Pubblicare e federarsi" },
  { id: "step-8", label: "8 — Mantenere e coltivare il riuso" },
  { id: "checklist", label: "Checklist sintetica" },
  { id: "riferimenti", label: "Riferimenti normativi e risorse" },
];

export default function Page() {
  return (
    <article className="container py-5" style={{ maxWidth: 880 }}>
      <h1>Come avviare una politica di open data in un Comune: guida passo passo</h1>
      <p className="lead">
        Questa guida accompagna un Comune che parte <strong>da zero</strong> nell&apos;apertura del
        proprio patrimonio informativo. Mette insieme la parte amministrativa (delibere, regolamenti,
        responsabilità) e quella tecnica (formati, metadati, pubblicazione) senza dare nulla per
        scontato, sulla base della normativa italiana ed europea vigente e delle prassi dei portali
        nazionali.
      </p>
      <p>
        L&apos;idea di fondo: aprire i dati non è prima di tutto un problema tecnologico, ma un cambio
        di postura organizzativa. La tecnologia (un catalogo, un convertitore di formati) è la parte
        facile; la parte che fa la differenza è decidere chi è responsabile, quali dati aprire, con
        che ritmo e con quali garanzie verso i cittadini.
      </p>

      <div className="alert alert-info" role="note" style={{ borderLeft: "4px solid var(--color-primary)" }}>
        <strong>A chi serve questa pagina.</strong> Se la scheda di maturità del tuo ente segna{" "}
        <em>«Dato insufficiente»</em> o un punteggio molto basso, è perché sul catalogo nazionale non
        risultano (ancora) dataset valutabili. Non è un giudizio: è il punto di partenza tipico. Segui
        gli otto passi qui sotto per avviare la pubblicazione; i collegamenti dalla scorecard ti
        portano direttamente alla sezione che risolve ciascun gap.
      </div>

      {/* Indice */}
      <nav aria-label="Indice della guida" className="border rounded p-3 my-4" style={{ background: "var(--bs-light, #f8f9fa)" }}>
        <h2 className="h6 text-uppercase text-muted mb-2" style={{ letterSpacing: "0.06em" }}>
          In questa guida
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

      {/* ── Quadro ── */}
      <section id="quadro" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Il quadro di riferimento in due minuti</h2>
        <p>
          La norma cardine è il <strong>D.Lgs. 36/2006</strong>, che recepisce la Direttiva europea
          sull&apos;apertura dei dati e il riutilizzo dell&apos;informazione del settore pubblico,
          aggiornato dal <strong>D.Lgs. 200/2021</strong> (trasposizione della Direttiva (UE)
          2019/1024, la &laquo;Direttiva Open Data&raquo;). A questo si affianca il{" "}
          <strong>Codice dell&apos;Amministrazione Digitale (CAD, D.Lgs. 82/2005)</strong>, che
          definisce i dati di tipo aperto (disponibili a tutti, accessibili con tecnologie digitali,
          gratuiti), istituisce il Responsabile per la Transizione Digitale e impone l&apos;uso di
          formati aperti. Sul versante della trasparenza interviene il <strong>D.Lgs. 33/2013</strong>,
          che impone già oggi la pubblicazione in formato aperto di molti dati comunali.
        </p>
        <p>
          A livello europeo, il tassello più recente è il{" "}
          <strong>Regolamento di esecuzione (UE) 2023/138</strong> sui &laquo;dati di elevato
          valore&raquo; (High-Value Datasets), applicabile dal 9 giugno 2024: individua sei categorie
          di dati da rendere disponibili come open data con modalità rafforzate (API, licenze aperte
          specifiche, metadati standard). Le indicazioni operative sono raccolte nelle{" "}
          <strong>Linee Guida Open Data di AgID</strong> (2023, in attuazione dell&apos;art. 12 del
          D.Lgs. 36/2006): distinguono i requisiti obbligatori dalle raccomandazioni e coprono formati,
          metadati, licenze, pubblicazione e organizzazione.
        </p>
        <p>
          Tre principi attraversano tutto: i dati devono essere in <strong>formato aperto</strong>{" "}
          (pubblico, documentato, indipendente dagli strumenti necessari a usarlo),{" "}
          <strong>leggibili meccanicamente</strong> e disponibili <strong>gratuitamente</strong> (o al
          più ai costi marginali di riproduzione). Utili anche i principi FAIR (reperibilità,
          accessibilità, interoperabilità, riusabilità) e il modello a cinque stelle, che descrive la
          scala di maturità dal PDF online fino ai linked open data.
        </p>
      </section>

      {/* ── Step 1 ── */}
      <section id="step-1" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Step 1 — Costruire la governance e formalizzare la volontà politica</h2>
        <p>
          Il primo passo non si fa al computer ma in giunta. Senza un mandato chiaro e una
          responsabilità assegnata, ogni iniziativa open data si esaurisce dopo i primi mesi.
        </p>
        <p>
          Il punto di partenza è la nomina (o la verifica) del{" "}
          <strong>Responsabile per la Transizione Digitale (RTD)</strong>, obbligatoria per tutte le PA
          ex art. 17 del CAD. L&apos;RTD coordina la trasformazione digitale dell&apos;ente — inclusi
          accessibilità, riuso e open data — e deve essere una persona interna (esclusi i consulenti
          esterni). Di norma: la Giunta individua con delibera l&apos;Ufficio per la Transizione
          Digitale, poi il Sindaco nomina il responsabile con decreto o determina. Nei Comuni privi di
          dirigenti, le funzioni possono essere affidate a un dipendente apicale o a un titolare di
          posizione organizzativa.
        </p>
        <p>
          Attorno all&apos;RTD conviene costituire un <strong>gruppo di lavoro trasversale</strong>:
          i dati vivono dispersi negli uffici (tributi, anagrafe, urbanistica, lavori pubblici,
          ambiente, polizia locale). Servono almeno un referente per ciascun settore che produce dati
          significativi, il supporto del DPO per i profili privacy e, se presente, il referente dei
          sistemi informativi.
        </p>
        <p>
          Sul piano degli atti, due livelli. Una <strong>delibera di indirizzo</strong> della Giunta
          che dichiara l&apos;open data come politica dell&apos;amministrazione, fissa obiettivi e
          tempi e adotta una <strong>licenza di riferimento</strong>. E, idealmente, un{" "}
          <strong>regolamento comunale sulla valorizzazione del patrimonio informativo</strong>, che
          disciplina in modo stabile ruoli, processi di pubblicazione, criteri di qualità e gestione
          delle richieste di riutilizzo. Il regolamento non è obbligatorio per partire, ma rende il
          processo ripetibile e indipendente dalle persone.
        </p>
      </section>

      {/* ── Step 2 ── */}
      <section id="step-2" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Step 2 — Censire il patrimonio informativo</h2>
        <p>
          Non si può aprire ciò che non si sa di avere. Il secondo passo è una{" "}
          <strong>ricognizione sistematica dei dati</strong> detenuti dall&apos;ente, settore per
          settore.
        </p>
        <p>
          Per ciascun insieme di dati il gruppo annota poche informazioni essenziali: di cosa si tratta
          e a cosa serve, quale ufficio lo detiene, in quale sistema o formato è conservato (un
          gestionale, un foglio di calcolo, un database), con quale frequenza viene aggiornato, se
          contiene dati personali e a quale base normativa risponde. Non serve la perfezione: serve una
          mappa onesta dello stato di fatto.
        </p>
        <p>
          La ricognizione fa emergere i dataset &laquo;facili&raquo; — già strutturati e senza
          criticità privacy — da cui conviene cominciare, e al tempo stesso i silos, le duplicazioni e
          i dati di bassa qualità su cui lavorare nel tempo. Scoprire che molti dati esistono solo in
          PDF o dentro applicativi chiusi è il punto di partenza tipico, non un fallimento.
        </p>
      </section>

      {/* ── Step 3 ── */}
      <section id="step-3" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Step 3 — Scegliere e prioritizzare i primi dataset</h2>
        <p>
          Aprire tutto subito è un errore: si rischia di pubblicare male e di perdere slancio. Meglio
          selezionare un primo nucleo di dataset ad alto valore e basso attrito.
        </p>
        <p>
          Tre criteri aiutano a scegliere. Il primo è l&apos;<strong>obbligo normativo</strong>: alcuni
          dati vanno comunque pubblicati in formato aperto per la trasparenza (contratti e appalti,
          bilanci, contributi e sovvenzioni, ex D.Lgs. 33/2013), quindi tanto vale farlo bene come open
          data. Il secondo è l&apos;appartenenza alle <strong>categorie di dati di elevato valore</strong>{" "}
          del Regolamento (UE) 2023/138: dati geospaziali, osservazione della terra e ambiente,
          meteorologici, statistici, su imprese e proprietà, sulla mobilità. Per un Comune i più
          ricorrenti sono i geospaziali (toponomastica, numeri civici, aree verdi, piano urbanistico) e
          quelli sulla mobilità (trasporto pubblico locale in formato GTFS, ZTL, parcheggi). Il terzo è
          la <strong>domanda reale</strong>: quali dati chiedono cittadini, associazioni, giornalisti,
          imprese e altri uffici.
        </p>
        <p>
          Una buona prima ondata per un piccolo o medio Comune: punti di interesse e servizi sul
          territorio, dati di bilancio strutturati, orari e fermate del trasporto pubblico, aree verdi
          e spazi pubblici, dati su rifiuti e raccolta differenziata. Dataset comprensibili, utili e
          generalmente privi di dati personali.
        </p>
      </section>

      {/* ── Step 4 ── */}
      <section id="step-4" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Step 4 — Bonifica, tutela della privacy e qualità</h2>
        <p>
          Prima di pubblicare, ogni dataset va preparato. È il passaggio che protegge l&apos;ente e i
          cittadini, e quello più spesso sottovalutato.
        </p>
        <p>
          La verifica più importante riguarda i <strong>dati personali</strong>. Gli open data sono per
          definizione riutilizzabili da chiunque, anche per fini commerciali: tutto ciò che permette di
          identificare una persona, direttamente o indirettamente, va escluso o efficacemente
          anonimizzato. Anonimizzare non è cancellare il nome: occorre evitare anche le combinazioni di
          campi che, incrociati, riconducono a un individuo. Nei casi dubbi si coinvolge il DPO e, se
          opportuno, si svolge una valutazione d&apos;impatto. Meglio rinunciare a un dato che
          pubblicarne uno re-identificabile.
        </p>
        <p>
          In parallelo si lavora sulla <strong>qualità</strong>: coerenza dei valori, campi obbligatori
          presenti, date e riferimenti corretti, assenza di duplicati ed errori sistematici. Conviene
          fissare una struttura stabile dei file (intestazioni chiare e costanti, codifiche standard,
          unità di misura esplicite): chi riutilizza i dati costruisce applicazioni che si rompono se la
          struttura cambia a ogni aggiornamento.
        </p>
      </section>

      {/* ── Step 5 ── */}
      <section id="step-5" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Step 5 — Formati aperti e licenza</h2>
        <p>
          Le Linee Guida sono chiare: i dati devono essere in formato aperto e leggibile meccanicamente.
          Concretamente, preferire <strong>CSV o JSON</strong> ai fogli di calcolo proprietari e, per i
          dati geografici, formati come <strong>GeoJSON, GML o Shapefile</strong>. Il PDF, salvo quando
          è inevitabile per i documenti, non è un buon formato aperto: i dati non se ne estraggono
          agevolmente. Per i dati di elevato valore il Regolamento europeo chiede in più la
          disponibilità tramite <strong>API</strong> e il download massivo (bulk download).
        </p>
        <p>
          Sulla <strong>licenza</strong> la regola d&apos;oro è la massima apertura compatibile con le
          esigenze dell&apos;ente. Le opzioni standard sono la dedica al pubblico dominio (<strong>CC0</strong>),
          che azzera ogni restrizione, oppure la Creative Commons Attribuzione (<strong>CC BY 4.0</strong>),
          che consente qualsiasi riuso chiedendo solo di citare la fonte; in Italia è diffusa anche la
          IODL 2.0, assimilabile a una CC BY. Per i dati di elevato valore il Regolamento (UE) 2023/138
          impone proprio CC0 o CC BY 4.0 (o licenze equivalenti o meno restrittive). La scelta va fatta
          una volta sola, dichiarata nella delibera e applicata uniformemente a tutto il catalogo.
        </p>
      </section>

      {/* ── Step 6 ── */}
      <section id="step-6" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Step 6 — Metadatare secondo DCAT-AP_IT</h2>
        <p>
          Un dato senza metadati è un dato che nessuno troverà. I metadati descrivono il dataset:
          titolo, descrizione, ente titolare, tema, frequenza di aggiornamento, licenza, punto di
          contatto, formato delle distribuzioni.
        </p>
        <p>
          In Italia lo standard obbligatorio è il profilo <strong>DCAT-AP_IT</strong>, estensione
          nazionale dello standard europeo DCAT-AP. Adottarlo è la condizione perché il dataset
          confluisca nel catalogo nazionale e, da lì, nel portale europeo. Il profilo modella il
          catalogo dell&apos;ente, i dataset e le distribuzioni (i singoli file o servizi), ciascuno con
          proprietà precise; esistono guide pratiche con esempi nelle diverse serializzazioni (JSON-LD,
          RDF/XML, Turtle). Per i dati territoriali si applicano inoltre i modelli INSPIRE e va
          alimentato il Repertorio Nazionale dei Dati Territoriali (RNDT).
        </p>
        <p>
          Consiglio pratico: non metadatare a mano file per file, ma adottare uno strumento (vedi passo
          successivo) che gestisca i metadati in modo conforme fin dall&apos;origine.
        </p>
      </section>

      {/* ── Step 7 ── */}
      <section id="step-7" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Step 7 — Pubblicare e federarsi con il catalogo nazionale</h2>
        <p>
          I dati vanno messi online in un <strong>catalogo</strong> consultabile, non sparsi in pagine
          diverse del sito.
        </p>
        <p>
          Lo strumento di riferimento per gli enti italiani è <strong>CKAN</strong>, la piattaforma open
          source su cui si basa anche il portale nazionale; un plugin la rende conforme al profilo
          DCAT-AP_IT. Un Comune può attivare una propria istanza CKAN (anche tramite soluzioni regionali
          o fornitori) oppure aderire a un catalogo aperto messo a disposizione da Regione o enti
          sovracomunali, spesso la via più rapida ed economica per i Comuni piccoli.
        </p>
        <p>
          Quando il catalogo è online e i metadati sono conformi, si procede alla{" "}
          <strong>federazione con dati.gov.it</strong> tramite <em>harvesting</em>: il catalogo
          nazionale interroga periodicamente in automatico quello del Comune e ne importa i metadati. La
          prima volta l&apos;amministrazione comunica alla redazione di dati.gov.it l&apos;URL del
          proprio catalogo e la modalità di harvesting (RDF DCAT-AP_IT, CKAN o CSW). Da lì gli
          aggiornamenti sono raccolti automaticamente e i metadati confluiscono anche nel portale europeo
          (data.europa.eu). Un controllo utile prima di chiedere la federazione è verificare il file
          dei metadati esposto dal catalogo (tipicamente a un indirizzo come{" "}
          <code>dati.comune.xxxx.it/catalog.rdf</code>).
        </p>
      </section>

      {/* ── Step 8 ── */}
      <section id="step-8" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Step 8 — Mantenere, aggiornare e coltivare il riuso</h2>
        <p>
          La pubblicazione non è il traguardo: è l&apos;inizio. Un catalogo che non si aggiorna perde
          valore e credibilità in pochi mesi.
        </p>
        <p>
          Sul piano della <strong>manutenzione</strong>, per ogni dataset va dichiarata e rispettata una
          frequenza di aggiornamento. Quando i dati nascono da un applicativo gestionale,
          l&apos;obiettivo a tendere è automatizzare l&apos;estrazione e l&apos;aggiornamento, così che
          la pubblicazione non dipenda dal lavoro manuale di una persona. Conviene monitorare l&apos;uso
          del catalogo (dataset più scaricati, richieste ricorrenti) per orientare le ondate successive.
        </p>
        <p>
          Sul piano della <strong>relazione con chi riutilizza i dati</strong>, vale la pena predisporre
          un canale per le richieste di nuovi dataset e per le segnalazioni di errori, e dare visibilità
          ai riusi concreti: applicazioni, analisi, progetti civici nati dai dati del Comune. Mostrare
          che i dati servono davvero è ciò che tiene viva la politica open data dentro l&apos;ente.
        </p>
        <p>
          Infine, l&apos;ente dovrebbe inserire l&apos;open data nel proprio{" "}
          <strong>Piano triennale per l&apos;informatica</strong> e svolgere una revisione periodica del
          catalogo, ampliando la copertura verso i dati di elevato valore e i livelli più alti del
          modello a cinque stelle.
        </p>
      </section>

      {/* ── Checklist ── */}
      <section id="checklist" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Checklist sintetica del percorso</h2>
        <ol style={{ fontSize: 15 }}>
          <li>Verificare la nomina dell&apos;RTD e costituire il gruppo di lavoro trasversale.</li>
          <li>
            Approvare la delibera di indirizzo con la scelta della licenza e, se possibile, adottare un
            regolamento comunale.
          </li>
          <li>Censire il patrimonio informativo settore per settore.</li>
          <li>Selezionare la prima ondata di dataset secondo obbligo, valore e domanda.</li>
          <li>Bonificare i dati, verificare i profili privacy con il DPO e validarne la qualità.</li>
          <li>Convertire in formati aperti e applicare la licenza scelta.</li>
          <li>Metadatare secondo DCAT-AP_IT.</li>
          <li>Pubblicare su un catalogo (CKAN o catalogo regionale) e federarsi con dati.gov.it via harvesting.</li>
          <li>Impostare aggiornamento, monitoraggio e ascolto dei riutilizzatori, e pianificare le ondate successive.</li>
        </ol>
      </section>

      {/* ── Riferimenti ── */}
      <section id="riferimenti" className="mt-5" style={{ scrollMarginTop: 80 }}>
        <h2>Riferimenti normativi e risorse operative</h2>

        <h3 className="h5 mt-4">Normativa</h3>
        <p style={{ fontSize: 14 }}>
          D.Lgs. 36/2006 come modificato dal D.Lgs. 200/2021 (riutilizzo dell&apos;informazione del
          settore pubblico); Direttiva (UE) 2019/1024 &laquo;Open Data&raquo;; Codice
          dell&apos;Amministrazione Digitale, D.Lgs. 82/2005 (in particolare artt. 17, 50, 52, 68);
          D.Lgs. 33/2013 (trasparenza, pubblicazione in formato aperto); Regolamento di esecuzione (UE)
          2023/138 sui dati di elevato valore; Direttiva 2007/2/CE INSPIRE e D.Lgs. 32/2010 per i dati
          territoriali.
        </p>

        <h3 className="h5 mt-4">Linee guida e guide pratiche</h3>
        <Riferimenti
          items={[
            { label: "Linee Guida Open Data di AgID (2023)", href: "https://www.agid.gov.it/it/ambiti-intervento/open-data" },
            { label: "AgID — Guida operativa sui dati di elevato valore", href: "https://www.agid.gov.it/it/agenzia/stampa-e-comunicazione/notizie/2023/12/22/open-data-online-guida-operativa-sui-dati-elevato-valore" },
            { label: "Profilo DCAT-AP_IT v1.0 (dati.gov.it)", href: "https://www.dati.gov.it/content/dcat-ap-it-v10-profilo-italiano-dcat-ap-0" },
            { label: "Linee guida per i cataloghi DCAT-AP_IT (docs.italia.it)", href: "https://docs.italia.it/italia/daf/linee-guida-cataloghi-dati-dcat-ap-it/it/stabile/" },
            { label: "Guida pratica all'adeguamento a DCAT-AP_IT (esempi)", href: "https://github.com/giorgialodi/Guida-pratica-DCAT-AP_IT" },
          ]}
        />

        <h3 className="h5 mt-4">Portali e strumenti</h3>
        <Riferimenti
          items={[
            { label: "Catalogo nazionale — Come alimentare il Catalogo", href: "https://www.dati.gov.it/Come-alimentare-il-Catalogo-nazionale" },
            { label: "dati.gov.it — FAQ per gli sviluppatori", href: "https://www.dati.gov.it/sviluppatori/faq" },
            { label: "Portale europeo dei dati aperti", href: "https://data.europa.eu" },
            { label: "CKAN — piattaforma open source per cataloghi", href: "https://ckan.org" },
            { label: "Repertorio Nazionale dei Dati Territoriali (RNDT)", href: "https://geodati.gov.it" },
          ]}
        />

        <h3 className="h5 mt-4">Figura RTD</h3>
        <Riferimenti
          items={[
            { label: "AgID — Responsabile per la Transizione al Digitale", href: "https://www.agid.gov.it/it/agenzia/responsabile-transizione-digitale" },
          ]}
        />
      </section>

      <p className="text-muted small mt-5">
        Questa guida ha carattere informativo e divulgativo; non sostituisce gli atti ufficiali né la
        consulenza legale. Fare sempre riferimento ai testi normativi e alle linee guida AgID vigenti.
      </p>
    </article>
  );
}
