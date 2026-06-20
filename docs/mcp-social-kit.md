# MCP server — kit per i social

Materiale **riservato** per la comunicazione: descrizioni brevi e bozze di post
pronte da adattare quando si scrivono i post sui social. NON è incluso nei
README pubblici dei singoli server (lì resta solo la documentazione tecnica).

Per ogni server MCP del progetto **opendata-ai**: una descrizione sintetica, una
bozza di post (LinkedIn/X) e gli hashtag. Adattali liberamente prima di
pubblicare.

---

## ckan-mcp-server

**Descrizione breve.** Wrapper FastMCP che espone i tool dell'Action API di CKAN
a qualunque client MCP, con un argomento `base_url` per-chiamata: una sola
immagine interroga qualsiasi portale open data CKAN (dati.gov.it, data.gov.uk,
data.gov, open.canada.ca…). Cerca dataset, legge metadati, naviga
organizzazioni/gruppi, interroga tabelle DataStore anche in SQL read-only.

**Post.** Un solo server MCP, qualsiasi catalogo open data del mondo. Abbiamo
costruito **ckan-mcp-server**: un wrapper FastMCP che espone l'Action API di CKAN
a Claude e a qualunque client MCP. La chiave? Ogni chiamata accetta un `base_url`
— quindi la stessa identica immagine interroga dati.gov.it, data.gov.uk, data.gov
o open.canada.ca senza un solo redeploy. Cerca dataset, leggi metadati, interroga
tabelle DataStore in SQL: gli open data civici diventano una conversazione. Open
source, fa parte del progetto opendata-ai. 🇮🇹🇪🇺

**Hashtag.** `#opendata #MCP #CKAN #AI #datigovit #civictech #LLM #ModelContextProtocol`

---

## istat-mcp-server (SDMX · ISTAT · Eurostat · OECD)

**Descrizione breve.** Una sola interfaccia SDMX per le statistiche ufficiali di
ISTAT, Eurostat e OECD, esposta a qualsiasi LLM via MCP. Wrapper FastMCP sulle API
REST SDMX 2.1: la stessa immagine interroga tutte e tre le fonti cambiando solo
gli argomenti `agency` / `base_url`.

**Post.** Le statistiche ufficiali di ISTAT, Eurostat e OECD ora parlano la lingua
dei tuoi agenti AI. 🇮🇹🇪🇺 Abbiamo costruito **istat-mcp**, un server MCP che
espone le API SDMX 2.1 come strumenti pronti per qualsiasi LLM: scopri i dataflow,
ispeziona le strutture, scarichi i dati in CSV — il tutto con citazione della
fonte. Il bello? **Una sola immagine** interroga ISTAT, Eurostat e OECD: cambia
solo l'agenzia. Open source, parte del progetto opendata-ai. 🚀

**Hashtag.** `#opendata #MCP #SDMX #ISTAT #Eurostat #OECD #AI #DataEngineering`

---

## osm-mcp (OpenStreetMap)

**Descrizione breve.** Geocoding, punti di interesse, routing e profili
territoriali di OpenStreetMap esposti come strumenti MCP. Trasforma anche un
GeoJSON in una pagina HTML Leaflet+OSM self-contained: un agente parte da un
indirizzo, scopre cosa c'è intorno, calcola un percorso e restituisce una mappa
navigabile senza scrivere JavaScript.

**Post.** Geocoding, POI, routing e zone territoriali di OpenStreetMap, ora come
strumenti MCP. Un agente AI parte da un indirizzo, scopre cosa c'è intorno,
calcola il percorso e restituisce una mappa Leaflet interattiva self-contained —
dai dati geografici a una mappa navigabile, senza scrivere JavaScript. Open
source, dati OSM sotto ODbL, parte del progetto opendata-ai.

**Hashtag.** `#GIS #geospatial #AI #opendata #LLM #OSM`

---

## opencoesione-mcp-server

**Descrizione breve.** Server MCP che rende l'evidenza finanziaria della politica
di coesione italiana interrogabile da un agente AI: espone OpenCoesione (progetti
finanziati dalle politiche di coesione UE e nazionali) come strumenti per LLM.
Risponde a domande di trasparenza sulla spesa pubblica di coesione (quanto
finanziato vs effettivamente speso, su quali territori e temi).

**Post.** 💶 Quanto è stato finanziato e quanto davvero **speso** dalle politiche
di coesione nel tuo Comune? Ora la trasparenza sui fondi di coesione è
**interrogabile da un agente AI**: abbiamo aperto OpenCoesione come server #MCP
dentro opendata-ai. Risolvi un territorio, leggi la capacità di spesa storica,
scava nei singoli progetti — con fonte e licenza citate ad ogni risposta. Soldi
pubblici, numeri verificabili. 🇮🇹

**Hashtag.** `#OpenCoesione #opendata #MCP #trasparenza #PA #AI #coesione #civictech`

---

## ispra-mcp-server (IdroGEO)

**Descrizione breve.** Server MCP che trasforma la piattaforma ISPRA IdroGEO in
uno strumento interrogabile da un agente AI: passando un codice ISTAT di comune
restituisce in una chiamata le percentuali di superficie e la popolazione esposta
per ogni classe di pericolosità da frana e alluvione, con citazione della fonte.

**Post.** 🏔️🌊 Il **rischio idrogeologico dei comuni italiani** ora è
interrogabile da un agente AI. Abbiamo incapsulato la piattaforma **ISPRA IdroGEO**
in un server **MCP**: passi un codice ISTAT e ottieni in una chiamata quanta
superficie comunale è a pericolosità da frana (P3+P4) o alluvione (P3/P2/P1) e
quante persone sono esposte — con la fonte già citata. Frane e alluvioni
diventano così **vincoli di pianificazione** che un'analisi territoriale
automatica può considerare al volo. Open data + MCP = decisioni più informate, in
chiaro. Parte del progetto open-source **opendata-ai**. 🇮🇹

**Hashtag.** `#ISPRA #IdroGEO #rischioidrogeologico #opendata #MCP #AI #PA #frane`

---

## maturity-mcp-server (ODM 2025)

**Descrizione breve.** Una scorecard di maturità open-data — modello ODM 2025 —
esposta come tool MCP. Misura la maturità open-data di una PA: harvest dei dataset
da un portale CKAN, valutazione qualità (5-star/FAIR/DCAT-AP_IT/ISO 25012/HVD),
aggregazione in 4 dimensioni + livello di maturità e raccomandazioni azionabili.

**Post.** 🇮🇹 Quanto sono *davvero* aperti e riusabili gli open data del tuo
Comune? Abbiamo messo **una scorecard di maturità open-data ODM 2025 dentro un tool
MCP**: fa harvest dei dataset da CKAN, li valuta su 5-star, FAIR, DCAT-AP_IT, ISO
25012 e HVD, e restituisce 4 dimensioni + livello (Beginner → Trend-setter) +
raccomandazioni azionabili. Lo colleghi a Claude Desktop e chiedi, in linguaggio
naturale: *"valuta la maturità open data di questo ente"*. Scoring 100%
deterministico, fail-safe, multi-portale. Parte di **opendata-ai**. 🚀

**Hashtag.** `#opendata #ODM #maturity #MCP #PA #AI #dataquality #DCAT`

---

## web-mcp (SearXNG)

**Descrizione breve.** La ricerca sul web come tool MCP — wrapper FastMCP che
espone due strumenti (`web_search` e `web_fetch`) appoggiati a un'istanza SearXNG
self-hosted, per portare nell'agente "cosa fanno gli altri enti" senza incollare
link a mano né API key proprietarie.

**Post.** 🔎 Abbiamo trasformato la **ricerca sul web in un tool MCP**. In
**opendata-ai** l'agente non si limita ai dataset: per la sorgente *marketing
territoriale* deve sapere *cosa fanno gli altri enti*. Così abbiamo costruito
**web-mcp**: un wrapper FastMCP che espone `web_search` e `web_fetch` appoggiati a
un'istanza **SearXNG self-hosted**. 👉 Niente API key proprietarie, niente query
verso terzi: la web search è self-hosted e arriva all'LLM come un normale tool MCP.
Stdio per Claude Desktop, streamable-HTTP in produzione. Stessa immagine. Risultato:
l'agente trova un precedente in un altro comune, ne apre la pagina e la cita, in
autonomia. 🌐

**Hashtag.** `#MCP #SearXNG #websearch #selfhosted #privacy #AI #opendata #FastMCP`
