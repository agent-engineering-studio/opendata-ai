
## API Notes — zone riconosciute (discovery 2026-06-12, spec 06)

- I confini comunali italiani (`admin_level=8`) portano `ref:ISTAT`
  **zero-padded** ("072006") → match diretto col `cod_comune` dello stack.
- Resa per tipo eterogenea: Bari ha 137 aree `landuse=industrial` (57 nominate;
  la "Zona Industriale di Bari" è una **relation** multipolygon), Barletta ha il
  porto reale ma NON taggato `landuse=harbour`. L'ordinamento è nominate-prima,
  poi area decrescente.
- Il **centro storico non è mappato come `place`** nemmeno a Bari, e Nominatim
  su "centro storico <comune>" può ritornare un guest house → il fallback
  filtra per class `place|boundary|landuse|leisure`; livello 3 = degradazione
  onesta all'analisi comunale.
- Le istanze pubbliche Overpass **throttlano** (429) e vanno in 504 sotto
  carico: il layer zone fa retry con backoff e cache TTL 24h.
- Tool: `osm_lookup_comune`, `osm_list_zones` (lista senza geometrie),
  `osm_get_zone` (Feature GeoJSON completa). Output con blocco `sources`
  ODbL e `source_url` citabile per entità.

## Configurazione — endpoint Overpass / Nominatim / OSRM

`osm-mcp` **non** parla con Overpass direttamente: usa `opendata_core.osm`, che
risolve gli endpoint da variabili d'ambiente (lette una volta all'avvio). La
POST resiliente `client.overpass_post` fa **retry con backoff + rotazione** tra
primario e fallback, con cache TTL 24h sul layer zone.

| Env | Default | Note |
|---|---|---|
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | endpoint primario |
| `OVERPASS_FALLBACK_URLS` | `https://overpass.kumi.systems/api/interpreter` | comma-separated, in rotazione |
| `NOMINATIM_URL` | `https://nominatim.openstreetmap.org` | geocoding |
| `OSRM_URL` | `https://router.project-osrm.org` | routing |
| `OSM_USER_AGENT` / `OSM_CONTACT_EMAIL` | — | identificazione (usage policy) |

**Mirror pubblici.** I default upstream (`overpass-api.de`, `kumi.systems`) sono
spesso bloccati in egress (ConnectError/timeout) o throttlano (429). Nel compose
del repo sono già impostati su mirror raggiungibili — FR (primario) + CH
(fallback):

```yaml
OVERPASS_URL: https://overpass.openstreetmap.fr/api/interpreter
OVERPASS_FALLBACK_URLS: https://overpass.osm.ch/api/interpreter
```

**Overpass self-hosted (consigliato in produzione).** Per togliere del tutto
rate limit e dipendenza dai mirror pubblici, lo stack include un servizio
`overpass` (immagine `wiktorn/overpass-api`, estratto Italia). `osm-mcp` lo usa
puntandoci le stesse env — nessuna modifica al codice:

```yaml
OVERPASS_URL: http://overpass/api/interpreter           # hostname del servizio compose
OVERPASS_FALLBACK_URLS: https://overpass.openstreetmap.fr/api/interpreter
```

Avvio: `make up` lo include di default (`make up OVERPASS=0` per escluderlo),
oppure `make overpass-up` per la sola istanza. Sizing (~25-50 GB), init iniziale
(~1-2h) e dettagli operativi: vedi **`infra/overpass/README.md`**. In produzione
il servizio è nell'overlay `agent-engineering-studio-infra` sotto profilo
`overpass`.
