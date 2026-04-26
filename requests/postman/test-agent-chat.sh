#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8002}"
PASS=0
FAIL=0

run_test() {
  local label="$1"
  local body="$2"
  local http_code

  curl_out=$(curl -s -o /tmp/ckan_resp.json \
    -w "%{http_code} %{size_download} %{time_total}" \
    -X POST "${BASE_URL}/chat" \
    -H "Content-Type: application/json" \
    -d "$body")
  read -r http_code size_bytes time_total <<< "$curl_out"
  size_kb=$(python3 -c "print(round(${size_bytes}/1024,2))")

  if [[ "$http_code" == "200" ]]; then
    echo "[PASS] $label"
    echo "  POST ${BASE_URL}/chat [200 OK, ${size_kb}kB, ${time_total}s]"
    python3 - <<'PYEOF'
import json, sys

d = json.load(open('/tmp/ckan_resp.json'))
text = d.get('text', '')
resources = d.get('resources', [])

print()
print("  TEXT")
print("  " + "-" * 72)
for line in text.splitlines():
    print("  " + line)
print()
print(f"  RESOURCES ({len(resources)})")
print("  " + "-" * 72)
for r in resources:
    print(f"  name   : {r.get('name','')}")
    print(f"  url    : {r.get('url','')}")
    print(f"  format : {r.get('format','')}")
    content = r.get('content')
    if content is not None:
        preview_lines = content.splitlines()[:5]
        print("  content:")
        for line in preview_lines:
            print("    " + line)
        if len(content.splitlines()) > 5:
            print(f"    ... ({len(content.splitlines())} lines total)")
    else:
        print("  content: (null — not downloaded)")
    print()
PYEOF
    ((PASS++))
  else
    echo "[FAIL] $label - HTTP $http_code"
    ((FAIL++))
  fi
  echo "  ════════════════════════════════════════════════════════════════════════"
  echo ""
}

# ── Health check ──────────────────────────────────────────────────
echo "=== Health Check ==="
health=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health")
if [[ "$health" == "200" ]]; then
  echo "[PASS] GET /health"
  ((PASS++))
else
  echo "[FAIL] GET /health - HTTP $health"
  ((FAIL++))
fi
echo ""

# ── Discovery ─────────────────────────────────────────────────────
echo "=== Discovery ==="

run_test "Cerca dataset sull'ambiente" \
  '{"query": "Cerca 5 dataset che riguardano l'\''ambiente e l'\''inquinamento."}'

run_test "Cerca dataset sui trasporti" \
  '{"query": "Cerca dataset relativi ai trasporti pubblici."}'

run_test "Cerca dataset sulla sanità" \
  '{"query": "Elenca dataset disponibili sul tema della sanità."}'

run_test "Cerca dataset sulla popolazione" \
  '{"query": "Cerca dataset sulla popolazione residente per quartiere e per classe di età."}'

# ── Package detail ────────────────────────────────────────────────
echo "=== Package detail ==="

run_test "Dettaglio dataset Popolazione residente" \
  '{"query": "Mostrami i dettagli completi (risorse, tag, organizzazione) del dataset con id '\''2908fe96-58c4-40fe-8b29-9d4d78715ba7'\''."}'

run_test "Risorse del dataset Popolazione residente" \
  '{"query": "Quali risorse sono disponibili nel dataset '\''2908fe96-58c4-40fe-8b29-9d4d78715ba7'\''? Elenca formato e URL di ciascuna."}'

# ── Organizations ─────────────────────────────────────────────────
echo "=== Organizations ==="

run_test "Lista organizzazioni" \
  '{"query": "Elenca le prime 10 organizzazioni presenti sul portale dati.gov.it."}'

run_test "Dettaglio organizzazione" \
  '{"query": "Mostrami i dettagli dell'\''organizzazione ISTAT sul portale e quanti dataset possiede."}'

# ── Groups / Categories ──────────────────────────────────────────
echo "=== Groups / Categories ==="

run_test "Lista gruppi tematici" \
  '{"query": "Quali gruppi tematici (categorie) sono disponibili sul portale?"}'

run_test "Dettaglio gruppo" \
  '{"query": "Mostrami i dataset nel gruppo '\''economia'\'' (o il gruppo tematico più simile)."}'

# ── Tags ──────────────────────────────────────────────────────────
echo "=== Tags ==="

run_test "Cerca tag popolazione" \
  '{"query": "Cerca i tag che contengono la parola '\''popolazione'\''."}'

# ── DataStore queries ─────────────────────────────────────────────
echo "=== DataStore queries ==="

run_test "Query su risorsa DataStore" \
  '{"query": "Cerca un dataset con dati tabulari (DataStore) sulla popolazione e mostrami le prime 5 righe."}'

run_test "DataStore con filtro" \
  '{"query": "Se esiste un dataset DataStore sui comuni italiani, filtra per la regione Lombardia e mostrami i primi risultati."}'

# ── Multi-step ────────────────────────────────────────────────────
echo "=== Multi-step (discovery -> detail -> data) ==="

run_test "Flusso completo autonomo" \
  '{"query": "Voglio capire quali dati aperti ci sono sulla qualità dell'\''aria in Italia. Cerca i dataset, scegline uno interessante, mostrami le risorse e se possibile scarica qualche riga di dati."}'

run_test "Esplorazione portale esterno (UK)" \
  '{"base_url": "https://data.gov.uk", "query": "Search for datasets about air quality in the UK and show me the first 3 results with their resources."}'

run_test "Multi-portale (IT vs UK)" \
  '{"query": "Confronta il numero di dataset disponibili sul portale italiano dati.gov.it con quelli del portale UK data.gov.uk."}'

# ── Site diagnostics ──────────────────────────────────────────────
echo "=== Site diagnostics ==="

run_test "Status del portale" \
  '{"query": "Verifica che il portale dati.gov.it sia raggiungibile e mostrami versione e estensioni installate."}'

run_test "Site read check" \
  '{"query": "Controlla se il portale dati.gov.it consente l'\''accesso pubblico in lettura."}'

# ── 1. AGRICOLTURA ────────────────────────────────────────────────
echo "=== 1. AGRICOLTURA ==="

run_test "AGR-1: Cerca dataset fattorie didattiche" \
  '{"query": "Cerca dataset sulle fattorie didattiche in Italia. Se ci sono file CSV o JSON, scaricali e mostrami il contenuto con gli URL di tutti i file collegati. Per gli altri formati fornisci solo l'\''URL."}'

run_test "AGR-2: Dataset agricoltura biologica" \
  '{"query": "Trova dataset sull'\''agricoltura biologica. Scarica e leggi eventuali file CSV, JSON o di testo e fornisci gli URL di tutte le risorse."}'

run_test "AGR-3: Aziende agricole" \
  '{"query": "Cerca dati aperti sulle aziende agricole italiane. Per i file CSV e JSON mostrami il contenuto, per tutti gli altri formati (XML, XSD, ODS) dammi solo l'\''URL."}'

run_test "AGR-4: Pesca e porti pugliesi" \
  '{"query": "Esistono dataset sulla pesca e i porti pugliesi? Cercali e se trovi file CSV scaricali e mostrami i dati. Per file XLSX fornisci solo l'\''URL."}'

run_test "AGR-5: Ristoranti e masserie" \
  '{"query": "Cerca dataset sui ristoranti o sulle masserie nel sud Italia. Scarica e leggi i file CSV trovati, fornendo URL per tutti i file collegati. Per i PDF solo URL."}'

# ── 2. ECONOMIA E FINANZE ─────────────────────────────────────────
echo "=== 2. ECONOMIA E FINANZE ==="

run_test "ECO-1: Edicole (dati geospaziali)" \
  '{"query": "Cerca dataset sulle edicole in Italia. Se ci sono file GeoJSON scaricali e mostrami il contenuto. Per SHP e WMS fornisci solo l'\''URL."}'

run_test "ECO-2: Attività estetiche" \
  '{"query": "Esistono dati aperti sulle attività estetiche? Cerca i dataset e per i file GeoJSON leggi il contenuto, per SHP e WMS dammi solo l'\''URL."}'

run_test "ECO-3: Lavoro cessazioni e avviamenti" \
  '{"query": "Cerca dataset sulle cessazioni e gli avviamenti di rapporti di lavoro. Scarica e leggi i file CSV trovati, mostrando gli URL di tutte le risorse collegate."}'

run_test "ECO-4: Mercato del lavoro - iscrizioni" \
  '{"query": "Trova dati aperti sulle iscrizioni ai centri per l'\''impiego. Scarica eventuali CSV e mostrami le prime righe con tutti gli URL."}'

run_test "ECO-5: Collocamento mirato disabili" \
  '{"query": "Ci sono dataset sul collocamento mirato per le categorie protette? Cercali e scarica i CSV trovati mostrando il contenuto e gli URL di tutti i file."}'

# ── 3. ISTRUZIONE, CULTURA E SPORT ───────────────────────────────
echo "=== 3. ISTRUZIONE, CULTURA E SPORT ==="

run_test "CUL-1: Anagrafe strutture scuole" \
  '{"query": "Cerca dataset sull'\''anagrafe delle strutture edilizie scolastiche. Scarica e leggi i file CSV, per ZIP e PDF fornisci solo l'\''URL."}'

run_test "CUL-2: Popolazione scolastica" \
  '{"query": "Trova dati sulla popolazione scolastica italiana. Se ci sono CSV scaricali e mostrami il contenuto. Per i PDF dammi solo l'\''URL."}'

run_test "CUL-3: Pendolarismo scolastico" \
  '{"query": "Cerca dataset sul pendolarismo scolastico. Scarica e leggi eventuali file CSV, per ZIP e RDF fornisci solo l'\''URL."}'

run_test "CUL-4: Alunni e classi per scuola" \
  '{"query": "Esistono dataset con il numero di alunni e classi per scuola? Trovane uno e scarica il CSV per mostrarmene il contenuto con tutti gli URL."}'

run_test "CUL-5: Ortofoto Cassero Fortezza Poggio Imperiale" \
  '{"query": "Cerca il dataset '\''Ortofoto Cassero Fortezza di Poggio Imperiale'\'' (id 1861198a-a961-41f5-86f3-aa8f351289b6). Mostrami i dettagli e gli URL delle risorse ZIP, TIF e WMS."}'

# ── 4. ENERGIA ────────────────────────────────────────────────────
echo "=== 4. ENERGIA ==="

run_test "ENE-1: Stazioni ricarica auto elettriche" \
  '{"query": "Cerca dataset sulle stazioni di ricarica per auto elettriche. Scarica e leggi i file CSV trovati, fornendo gli URL di tutte le risorse."}'

run_test "ENE-2: Punti luce pubblica illuminazione" \
  '{"query": "Trova dati aperti sui punti luce dell'\''illuminazione pubblica. Per i file CSV scarica e mostra il contenuto. Per gli altri formati solo URL."}'

run_test "ENE-3: Comunità energetiche rinnovabili" \
  '{"query": "Ci sono dataset sulle Comunità Energetiche Rinnovabili (CER)? Cercali e scarica eventuali file CSV mostrando contenuto e URL."}'

run_test "ENE-4: Produzione impianti fotovoltaici" \
  '{"query": "Cerca dataset sulla produzione degli impianti fotovoltaici. Se ci sono file JSON o CSV scaricali e mostrami il contenuto con tutti gli URL collegati."}'

run_test "ENE-5: Consumi energia elettrica serie storica" \
  '{"query": "Trova la serie storica dei consumi di energia elettrica. Scarica e leggi i file JSON e CSV trovati, fornendo gli URL di tutte le risorse. Per XLS dammi solo l'\''URL."}'

# ── 5. AMBIENTE ───────────────────────────────────────────────────
echo "=== 5. AMBIENTE ==="

run_test "AMB-1: Aree verdi urbane" \
  '{"query": "Cerca dataset sulle aree verdi urbane. Per i file in formato WMS, KML, SHP fornisci solo l'\''URL. Se ci sono GeoJSON o CSV scaricali e mostra il contenuto."}'

run_test "AMB-2: Distributori di carburante" \
  '{"query": "Trova dati aperti sui distributori di carburante. Se ci sono file GeoJSON scaricali e mostrami il contenuto. Per SHP e WMS dammi solo l'\''URL."}'

run_test "AMB-3: Alberi da frutto in città" \
  '{"query": "Esistono dataset sugli alberi da frutto nelle città? Cercali e per i file SHP e KML fornisci solo l'\''URL."}'

run_test "AMB-4: Aree giochi" \
  '{"query": "Cerca dataset sulle aree giochi per bambini. Mostrami gli URL delle risorse KML, WMS e SHP trovate."}'

run_test "AMB-5: Faglie attive e pericolosità sismica" \
  '{"query": "Ci sono dati aperti sulle faglie attive o la pericolosità sismica? Cercali e mostrami gli URL di tutte le risorse disponibili."}'

# ── 6. GOVERNO E SETTORE PUBBLICO ─────────────────────────────────
echo "=== 6. GOVERNO E SETTORE PUBBLICO ==="

run_test "GOV-1: Area stradale (Comune di Vinci)" \
  '{"query": "Cerca il dataset '\''Area stradale'\'' del Comune di Vinci (id 8ad84dc3-da4e-4146-9ed6-ae5b7858bec4). Mostrami tutte le risorse con i loro URL. Per GeoJSON scarica e leggi il contenuto."}'

run_test "GOV-2: Destinazione d'uso catastale" \
  '{"query": "Trova dataset sulla destinazione d'\''uso catastale dei fabbricati. Per i file GeoJSON scarica e mostra il contenuto, per gli altri formati (ZIP, SHP, KML, GML) fornisci solo l'\''URL."}'

run_test "GOV-3: Norme Tecniche di Attuazione" \
  '{"query": "Cerca il dataset '\''Norme Tecniche di Attuazione'\'' (id da3db55b-b3f4-44fb-b4de-f1e5cf35c8fb). Scarica e leggi i file TXT, CSV e JSON. Per il PDF fornisci solo l'\''URL."}'

run_test "GOV-4: Consumo del suolo" \
  '{"query": "Trova dati aperti sul consumo del suolo. Per i file GeoJSON scaricali e mostra il contenuto. Per ZIP, GML, KML, SHP fornisci solo l'\''URL."}'

run_test "GOV-5: Aree di circolazione pedonale" \
  '{"query": "Cerca dataset sulle aree di circolazione pedonale. Mostrami gli URL di tutte le risorse disponibili (GeoJSON, KML, SHP, WFS, WMS)."}'

# ── 7. SALUTE ─────────────────────────────────────────────────────
echo "=== 7. SALUTE ==="

run_test "SAL-1: Turni farmacie Firenze" \
  '{"query": "Cerca il dataset sui turni delle farmacie a Firenze (id 36192da7-1b8f-4a7e-922e-f44ff405f5f2). Mostrami gli URL delle risorse WMS, KML e SHP."}'

run_test "SAL-2: Tassi assenze ASL Taranto" \
  '{"query": "Trova dataset sui tassi di assenze del personale ASL Taranto. Scarica e leggi i file CSV, per XLSX fornisci solo l'\''URL."}'

run_test "SAL-3: Progetti AReSS Puglia" \
  '{"query": "Cerca dataset sui progetti sanitari finanziati dell'\''AReSS Puglia. Scarica il CSV e mostrami il contenuto con l'\''URL."}'

run_test "SAL-4: Pazienti cronici diabete" \
  '{"query": "Esistono dati aperti sui pazienti cronici affetti da diabete in Puglia? Cerca il dataset, scarica il CSV e mostra le prime righe con l'\''URL."}'

run_test "SAL-5: Anagrafica Breast Unit Puglia" \
  '{"query": "Cerca il dataset '\''Anagrafica Breast Unit Puglia'\'' (id 1425110c-cac1-451c-9037-78fb87407378). Scarica e leggi i file JSON, GeoJSON e CSV, fornendo tutti gli URL."}'

run_test "SAL-6: Centri prescrizione diabete" \
  '{"query": "Trova il dataset sui centri autorizzati alla prescrizione di tecnologie per il diabete. Scarica il GeoJSON e il CSV, per il PDF dammi solo l'\''URL."}'

# ── 8. TEMATICHE INTERNAZIONALI ───────────────────────────────────
echo "=== 8. TEMATICHE INTERNAZIONALI ==="

run_test "INT-1: Progetti Interreg Pugliesi" \
  '{"query": "Cerca dataset sui progetti Interreg pugliesi. Scarica e leggi il file CSV mostrando contenuto e URL."}'

run_test "INT-2: Protocolli di intesa" \
  '{"query": "Trova dati aperti sui protocolli di intesa attivi del Comune di Lecce. Scarica il CSV e mostrami il contenuto con l'\''URL."}'

run_test "INT-3: Progetti finanziati con partner europei" \
  '{"query": "Cerca dataset sui progetti finanziati con risorse comunitarie e i relativi partner. Scarica il CSV e per il file XLS fornisci solo l'\''URL."}'

run_test "INT-4: Osservatorio Milano Benchmark" \
  '{"query": "Trova il dataset '\''Osservatorio Milano - Benchmark'\'' (id 6f0cfb53-742d-4044-b4ee-e0d67bffa68d). Scarica e leggi il CSV mostrando il contenuto con l'\''URL."}'

run_test "INT-5: Beneficiari Interreg IPA South Adriatic" \
  '{"query": "Cerca dati sui beneficiari del programma Interreg IPA South Adriatic. Scarica il CSV e mostrami i dati. Per il file XLSX fornisci solo l'\''URL."}'

# ── 9. GIUSTIZIA E SICUREZZA PUBBLICA ─────────────────────────────
echo "=== 9. GIUSTIZIA E SICUREZZA PUBBLICA ==="

run_test "GIU-1: Statistica incidenti stradali 2016" \
  '{"query": "Cerca il dataset sulla statistica degli incidenti stradali 2016 (id 75355832-91da-462a-b007-7072bc9d7c49). Scarica il CSV e mostrami i dati. Per XLS fornisci solo l'\''URL."}'

run_test "GIU-2: Località verbali incidenti" \
  '{"query": "Trova dataset sulle località dove sono avvenuti incidenti stradali. Scarica e leggi il CSV, per XLS dammi solo l'\''URL."}'

run_test "GIU-3: Violazioni codice della strada" \
  '{"query": "Cerca dati aperti sulle violazioni del codice della strada con relativi articoli. Scarica il CSV e mostra il contenuto con gli URL di tutte le risorse."}'

run_test "GIU-4: Sanzioni ambientali Polizia Locale" \
  '{"query": "Trova il dataset sulle sanzioni ambientali della Polizia Locale di Martina Franca. Scarica il CSV e per XLS fornisci solo l'\''URL."}'

run_test "GIU-5: Ricorsi al Prefetto" \
  '{"query": "Cerca dataset sui ricorsi al Prefetto contro i verbali del Codice della Strada. Scarica e leggi il file CSV mostrando contenuto e URL."}'

run_test "GIU-6: Ubicazione Photored" \
  '{"query": "Trova il dataset sull'\''ubicazione dei Photored semaforici nel territorio comunale (id df718a8e-b5fd-49da-9d2e-7df85a48d904). Scarica il CSV e mostrami le posizioni."}'

# ── 10. REGIONI E CITTÀ ───────────────────────────────────────────
echo "=== 10. REGIONI E CITTÀ ==="

run_test "REG-1: Toponimi Firenze" \
  '{"query": "Cerca il dataset dei toponimi ufficiali del Comune di Firenze (id 1a41df44-0d84-470c-ab5a-20999be49b2e). Scarica e leggi il CSV mostrando il contenuto con l'\''URL."}'

run_test "REG-2: Tratti stradali Firenze" \
  '{"query": "Trova il dataset sui tratti stradali della viabilità del Comune di Firenze. Per KML, SHP e WMS fornisci solo gli URL."}'

run_test "REG-3: Civici Firenze" \
  '{"query": "Cerca il dataset dei numeri civici del Comune di Firenze. Mostrami gli URL delle risorse SHP e WMS."}'

run_test "REG-4: Limiti amministrativi comunali" \
  '{"query": "Trova dataset sui limiti amministrativi comunali della Città Metropolitana di Firenze. Per ZIP e WMS fornisci solo l'\''URL."}'

run_test "REG-5: Carta Provinciale 1:10.000" \
  '{"query": "Cerca il dataset '\''Carta Provinciale 1:10.000'\'' della Città Metropolitana di Firenze (id 9b14e2fe-2f21-4d64-8508-876c9b00ad80). Mostrami gli URL di ZIP e WMS."}'

# ── 11. POPOLAZIONE E SOCIETÀ ─────────────────────────────────────
echo "=== 11. POPOLAZIONE E SOCIETÀ ==="

run_test "SOC-1: Popolazione residente per quartiere Firenze" \
  '{"query": "Cerca il dataset sulla popolazione residente per quartiere e classe di età di Firenze (id 2908fe96-58c4-40fe-8b29-9d4d78715ba7). Scarica e leggi il CSV, per PDF e XLSX dammi solo l'\''URL."}'

run_test "SOC-2: Individui residenti censimento" \
  '{"query": "Trova il dataset sugli individui residenti per sezione di censimento a Firenze. Scarica il CSV e mostra le prime righe. Per XLSX e PDF fornisci solo l'\''URL."}'

run_test "SOC-3: Famiglie residenti per censimento" \
  '{"query": "Cerca dati sulle famiglie residenti per sezione di censimento e quartiere. Scarica e leggi il CSV, per PDF e XLSX dammi solo gli URL."}'

run_test "SOC-4: Famiglie per numero componenti" \
  '{"query": "Trova dataset sulle famiglie residenti per numero di componenti a Firenze. Scarica il CSV e mostra il contenuto con tutti gli URL."}'

run_test "SOC-5: Stalli sosta disabili" \
  '{"query": "Cerca il dataset sugli stalli di sosta riservati ai disabili a Firenze (id 01a508c5-a5d0-420b-b7c9-8eb5e437978f). Mostrami gli URL delle risorse SHP, KML e WMS."}'

run_test "SOC-6: Movimenti turistici Firenze" \
  '{"query": "Trova dati sui movimenti turistici nella Città Metropolitana di Firenze. Per PDF e ZIP fornisci solo l'\''URL."}'

# ── 12. SCIENZA E TECNOLOGIA ──────────────────────────────────────
echo "=== 12. SCIENZA E TECNOLOGIA ==="

run_test "SCI-1: Punti accesso WiFi Firenze" \
  '{"query": "Cerca il dataset sui punti di accesso WiFi nella Città Metropolitana di Firenze. Per WMS e ZIP fornisci solo gli URL."}'

run_test "SCI-2: WiFi Comune di Firenze" \
  '{"query": "Trova il dataset WiFi del Comune di Firenze (id 8d829c58-1a8f-43e6-90ff-f2838ffe572c). Mostrami gli URL di WMS, SHP e KML."}'

run_test "SCI-3: Reti di Laboratori Puglia" \
  '{"query": "Cerca dataset sulle reti di laboratori in Puglia. Scarica e leggi i file CSV e JSON, per XLS e ODS fornisci solo l'\''URL."}'

run_test "SCI-4: Digital Divide" \
  '{"query": "Trova dati aperti sul digital divide. Scarica e leggi il file CSV mostrando il contenuto con l'\''URL."}'

run_test "SCI-5: Distretti tecnologici" \
  '{"query": "Cerca il dataset sui distretti tecnologici pugliesi (id 6602d578-a23a-497c-a876-5e1a663eb4d7). Scarica il CSV e mostrami i dati. Per ODS, XML, XSD fornisci solo l'\''URL."}'

run_test "SCI-6: Prezzario Regione Puglia 2024" \
  '{"query": "Trova il dataset '\''Prezzario Regione Puglia 2024'\'' . Scarica e leggi il file CSV mostrando contenuto e URL."}'

# ── 13. TRASPORTI ─────────────────────────────────────────────────
echo "=== 13. TRASPORTI ==="

run_test "TRA-1: Trasporto pubblico tempo reale Toscana" \
  '{"query": "Cerca il dataset sul trasporto pubblico in tempo reale della Regione Toscana. Mostrami i dettagli e l'\''URL della risorsa BIN."}'

run_test "TRA-2: Incidentalità percorsi ciclabili" \
  '{"query": "Trova dati sull'\''incidentalità sui percorsi ciclabili della Provincia di Pistoia. Per GeoJSON scarica e mostra il contenuto, per ZIP, GML, KML, SHP, WFS, WMS fornisci solo l'\''URL."}'

run_test "TRA-3: Ciclostazioni" \
  '{"query": "Cerca il dataset sulle ciclostazioni della Provincia di Pistoia (id e83ac204-fdb8-4d8e-89d4-a8f5bec8daa6). Per GeoJSON scarica e leggi il contenuto, per gli altri formati dammi solo l'\''URL."}'

run_test "TRA-4: Viabilità Provincia di Pistoia" \
  '{"query": "Trova il dataset sulla viabilità della Provincia di Pistoia. Per GeoJSON scarica e mostra il contenuto, per tutti gli altri formati (ZIP, GML, KML, SHP, WFS, WMS) fornisci solo l'\''URL."}'

run_test "TRA-5: Aree a ciclabilità diffusa" \
  '{"query": "Cerca dataset sulle aree a ciclabilità diffusa. Per GeoJSON scarica e leggi il contenuto, per KML, SHP, WFS, WMS dammi solo l'\''URL."}'

run_test "TRA-6: Svincoli FIPILI Firenze" \
  '{"query": "Trova il dataset sugli svincoli della FIPILI nella Città Metropolitana di Firenze (id 480fb1df-2c52-442e-a7d0-397316213538). Mostrami gli URL delle risorse WMS e ZIP."}'

# ── Summary ────────────────────────────────────────────────────────
echo "=== SUMMARY ==="
TOTAL=$((PASS + FAIL))
echo "Passed: $PASS / $TOTAL"
echo "Failed: $FAIL / $TOTAL"
[[ $FAIL -eq 0 ]]
