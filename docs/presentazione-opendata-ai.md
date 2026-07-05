# opendata-ai — dai dati pubblici a un'analisi del territorio

*Una presentazione del progetto per avviare una collaborazione con un'associazione di divulgazione scientifica sugli open data.*

---

## L'idea di fondo

Gli open data sono una delle grandi promesse mantenute a metà del decennio scorso:
oggi le pubbliche amministrazioni italiane ed europee pubblicano una quantità enorme di
informazioni — anagrafiche, statistiche, geografiche, di bilancio, ambientali. Eppure
chi prova davvero a usarle si scontra quasi subito con un muro. I dati vivono su portali
diversi, parlano linguaggi tecnici diversi, e per metterli in relazione servono
competenze che la maggior parte delle persone — e dei piccoli comuni — non ha. Il
risultato è un paradosso noto a chiunque si occupi di dati aperti: **i dati ci sono, ma
restano poco riusati**.

opendata-ai nasce per sciogliere questo nodo. È una piattaforma che interroga le fonti
ufficiali, le incrocia e ne ricava una lettura d'insieme comprensibile, restituendo non
un file da scaricare ma **un'analisi leggibile, con ogni affermazione ancorata alla sua
fonte**. L'obiettivo dichiarato non è sostituirsi all'amministratore o al ricercatore,
ma dargli un punto di partenza solido: una fotografia del territorio costruita
esclusivamente su dati pubblici e verificabili.

## Come funziona, in poche parole

Quando si chiede a opendata-ai di analizzare un comune, il sistema non si limita a una
singola banca dati. In parallelo va a leggere i portali open data nazionali e regionali
(lo standard CKAN), le banche dati statistiche di ISTAT, Eurostat e OECD (lo standard
SDMX), la cartografia collaborativa di OpenStreetMap, i progetti di coesione finanziati
con fondi europei e nazionali (OpenCoesione) e i dati sul rischio idrogeologico
dell'ISPRA. Ognuna di queste fonti, da sola, racconta un frammento; messe insieme
disegnano un quadro.

Il punto delicato di qualsiasi sistema di questo tipo è la fiducia. opendata-ai è
costruito attorno a un principio molto semplice da enunciare e molto impegnativo da
rispettare: **non si afferma nulla che non sia tracciabile fino a una fonte aperta**.
Ogni numero che compare in un'analisi porta con sé il link al dato originale; dove
un'informazione non è certa, viene esplicitamente etichettata come "da verificare"
invece di essere presentata come un fatto. E quando i dati semplicemente non bastano, il
sistema lo dichiara — "dato insufficiente" — invece di produrre punteggi rassicuranti ma
falsi. È una scelta di metodo prima che tecnica: meglio un'analisi che ammette i propri
limiti di una che li nasconde.

## Le otto lenti del territorio

Il cuore analitico del progetto sono le **otto lenti tematiche** con cui osserva un
comune: commercio, turismo, lavoro, trasporti, welfare e coesione sociale, ambiente e
rischio idrogeologico, istruzione, sanità. Ciascuna lente non è una semplice etichetta,
ma un connettore che attinge a fonti specifiche e pertinenti — i dati ISTAT sulla
struttura economica e sulla popolazione, gli orari e le fermate del trasporto pubblico,
le scuole del Ministero dell'Istruzione, le farmacie e i presìdi sanitari, i poligoni di
pericolosità idraulica dell'ISPRA, e così via. La lente sanità, per fare un esempio
concreto, distingue gli ospedali per acuti dai presìdi non acuti e, dove un ospedale non
c'è, calcola la distanza dalla struttura più vicina: un livello di onestà che evita di
spacciare un poliambulatorio per un pronto soccorso.

Messe insieme, le otto lenti producono un **report del comune**: un racconto descrittivo
del territorio con i suoi numeri, una lettura dei punti di forza e di debolezza, e una
serie di proposte di intervento. Qui opendata-ai fa un passo che lo distingue da un
semplice cruscotto di indicatori.

## Dalle analisi alle idee: la rigenerazione parametrica

Le proposte del report non sono generiche. Nascono da un motore di **rigenerazione
parametrica** che dimensiona ogni idea sui numeri reali del comune. Se la popolazione
richiede una certa dotazione di verde, di impianti sportivi, di aree mercatali o di
piste ciclabili, il sistema calcola l'obiettivo a partire dagli standard normativi — le
dotazioni minime di legge, i parametri dei piani urbani della mobilità sostenibile — e
confronta il fabbisogno teorico con ciò che esiste. Le idee vengono poi agganciate agli
**Obiettivi di Sviluppo Sostenibile** dell'Agenda 2030, così che ogni proposta sia
leggibile anche nel quadro più ampio della sostenibilità.

A questo si aggiunge la capacità di **individuare aree concrete** su cui quelle idee
potrebbero atterrare. Interrogando OpenStreetMap, il sistema cerca i vuoti urbani, le
aree dismesse, gli ex siti industriali o militari, i parcheggi riqualificabili, e li
classifica per idoneità tenendo conto della centralità e della distanza. Una rifinitura
recente ritaglia i candidati esattamente entro il confine comunale, eliminando il rumore
delle aree dei comuni vicini. E poiché in Italia non si può ragionare di rigenerazione
senza fare i conti con il dissesto, ogni proposta passa attraverso una verifica dei
**vincoli idrogeologici**: l'esito ISPRA a livello comunale viene riportato come parte
dell'analisi, non rimandato a un generico "da verificare".

## La qualità dei dati e la qualità dei report

opendata-ai non guarda solo *cosa* dicono i dati, ma anche *quanto bene* sono pubblicati.
Un modulo dedicato valuta la **maturità** dei dati di un ente secondo gli standard
riconosciuti a livello internazionale ed europeo — il modello a cinque stelle dei
Linked Open Data, i principi FAIR, il profilo italiano DCAT-AP_IT, gli indicatori di
qualità ISO. Ne ricava un punteggio articolato su più dimensioni, utile a un'amministrazione
per capire dove migliorare la propria pubblicazione di dati. È, in piccolo, un esercizio
di metariflessione sui dati aperti: usare i dati per misurare la qualità dei dati.

Specularmente, il progetto applica una **rubric di qualità ai report** che genera. Prima
di considerare pubblicabile un'analisi, una serie di controlli automatici verifica i
difetti tipici: dati troppo vecchi spacciati per attuali, denominatori incoerenti (la
stessa popolazione citata con numeri diversi in punti diversi), certificazioni di origine
asserite senza una fonte ufficiale, proposte duplicate, vincoli rimandati invece di
riportati. Questi controlli non bloccano il lavoro: lo annotano, segnalando con
trasparenza dove l'analisi è solida e dove va presa con cautela. Anche qui torna il filo
conduttore del progetto, cioè rendere visibile il proprio grado di affidabilità.

## L'intelligenza artificiale al posto giusto

opendata-ai usa modelli linguistici, ma con una divisione dei compiti netta e dichiarata.
**Il modello scrive, i dati decidono.** La prosa discorsiva — il racconto del territorio,
la motivazione di una proposta — è generata da un modello linguistico; ma i numeri, i
punteggi, i dimensionamenti e i vincoli sono calcolati in modo deterministico a partire
dalle fonti, senza che il modello possa alterarli. Questo confina l'IA al ruolo in cui è
più utile e meno rischiosa — la sintesi e la lingua — tenendola lontana da ciò che deve
restare verificabile.

Il modello, inoltre, è intercambiabile: può girare **in locale** sulla macchina
dell'ente, con vantaggi di privacy e costo nullo, oppure appoggiarsi a servizi cloud più
capaci quando serve un'analisi più ricca. La piattaforma adatta perfino il livello di
dettaglio del report alle capacità del modello disponibile, avvisando l'utente quando un
modello piccolo potrebbe essere meno affidabile.

## Una memoria del riuso, non un archivio di documenti

C'è infine una scelta concettuale che vale la pena raccontare a chi si occupa di cultura
del dato. opendata-ai considera gli **open data l'unica fonte ufficiale**: il comune non
carica documenti propri, non sovrascrive il dato pubblico. Ciò che il sistema accumula
nel tempo non sono file, ma **le analisi stesse** — la conoscenza prodotta diventa
riusabile, e ogni nuova lettura del territorio può poggiare su quelle precedenti. È un
modo di intendere il riuso che ribalta l'abitudine: non un ennesimo deposito di PDF, ma
una memoria viva delle interpretazioni. E quando un dato pubblico appare disallineato
dalla realtà — cosa che accade, per ragioni burocratiche — il sistema lo segnala come
occasione per sollecitarne l'aggiornamento, anziché aggirarlo.

Tutto questo è esposto sia attraverso una **mappa interattiva** pensata per la
consultazione, sia attraverso **API aperte** che permettono ad altri strumenti, ricerche
o agenti software di interrogare le stesse capacità. Il progetto, ad oggi, ha come pilota
di riferimento il comune di Gioia del Colle, in Puglia, circa 27.000 abitanti, su cui le
analisi sono state validate end-to-end con dati reali.

## Perché può interessare alla divulgazione scientifica

Chi fa divulgazione sugli open data lavora ogni giorno sul ponte tra il dato grezzo e la
persona che dovrebbe capirlo e usarlo. opendata-ai costruisce parte di quel ponte:
trasforma tabelle ostiche in narrazioni comprensibili, tenendo però sempre visibile il
filo che lega ogni frase al dato originale. È quindi al tempo stesso uno **strumento** da
mettere nelle mani del pubblico, un **oggetto di studio** — un caso concreto di metodo
trasparente, riproducibile e criticabile — e una **fonte di materiale divulgativo**, dal
momento che ogni report comunale è già una storia di dati pronta per essere raccontata in
un articolo, una lezione o un laboratorio.

La trasparenza metodologica del progetto, in particolare, lo rende adatto a un dialogo
con la comunità scientifica: poiché ogni risultato è tracciabile e ogni assunzione è
dichiarata, il metodo può essere discusso, messo alla prova e migliorato in pubblico —
esattamente il tipo di confronto che la divulgazione rigorosa sa innescare.

## Spunti per una collaborazione

Le strade possibili sono diverse e non si escludono a vicenda. La più immediata è una
**revisione condivisa delle metodologie** — i criteri di maturità dei dati, la rubric di
qualità dei report, i parametri di dimensionamento — su cui l'esperienza divulgativa di
un'associazione può alzare insieme il rigore e la chiarezza. C'è poi tutto il fronte dei
**contenuti**: schede, brevi guide alla lettura di un dato pubblico, articoli costruiti a
partire dai report generati. Sul piano delle attività, lo strumento si presta a
**laboratori ed eventi** di alfabetizzazione ai dati, di rigenerazione urbana, di scienza
dei dati civica. E sul piano tecnico, l'architettura è pensata per crescere: nuove lenti
tematiche o nuovi indicatori suggeriti dalla comunità scientifica possono essere
aggiunti senza riscrivere l'esistente.

In sintesi, opendata-ai è un'infrastruttura aperta per dare valore agli open data: fonti
ufficiali, metodo trasparente, risultati verificabili. Per un'associazione che fa
divulgazione scientifica sui dati aperti può diventare un terreno comune da cui far
partire qualcosa insieme — e questa presentazione vuole essere il primo passo di quella
conversazione.

---

*Contatto: Giuseppe Zileni — giuseppe.zileni@hevolus.it*
