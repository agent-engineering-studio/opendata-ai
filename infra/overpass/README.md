# Overpass self-hosted (opt-in)

Istanza Overpass locale su un estratto regionale OSM. Serve a togliere di mezzo
i due problemi cronici delle istanze pubbliche:

- **rate limit** (`429 Too Many Requests`) sotto carico;
- **blocco di rete in egress** — i default `overpass-api.de` + `overpass.kumi.systems`
  sono irraggiungibili da alcune reti (`ConnectError`/timeout), mentre i mirror
  pubblici FR/CH funzionano ma restano soggetti a throttling.

Con l'istanza locale ogni query Overpass (ancore zona/turismo del backend e tool
`osm_*` dell'osm-mcp) gira in LAN: nessun limite, ~20–50 ms, deterministica.
La cache Redis 24h sulle ancore (`opendata_backend.factory._lens_cached`) resta
utile anche così — taglia le query ripetute.

## Quando attivarla

Non è nel set di default: richiede disco e un init lungo. Attivala quando la
reliability di Overpass in produzione diventa critica. Per il resto, i mirror
pubblici FR/CH (default in `.env.local.example`) bastano.

## Sizing

| Scope | `.pbf` (download) | DB Overpass (`OVERPASS_META=no`) | Init a freddo |
|---|---|---|---|
| Italia (Sud — Puglia inclusa) | ~300–500 MB | ~5–12 GB | ~10–30 min |
| Italia intera (default) | ~2 GB | ~25–50 GB | ~1–2 h |

`OVERPASS_META=no` esclude metadata/attic (lo storico delle modifiche): l'app usa
solo geometrie e tag correnti, quindi il DB resta molto più piccolo. Il volume
Docker `opendata-ai-overpass-db` va dimensionato di conseguenza (sul VPS Aruba
controlla lo spazio prima di attivarlo).

## Avvio

```bash
# 1. attiva il profilo (scarica .pbf + build del DB: il container resta
#    NON pronto finché l'init non finisce — segui i log)
docker compose --profile overpass up -d overpass
docker compose logs -f overpass        # attendi "Database ready" / dispatcher up

# 2. punta i client (backend + osm-mcp) all'istanza locale — in .env/.env.local:
#    OVERPASS_URL=http://overpass/api/interpreter
#    OVERPASS_FALLBACK_URLS=https://overpass.openstreetmap.fr/api/interpreter
docker compose up -d opendata-backend osm-mcp
```

Verifica:

```bash
curl -s 'http://localhost:18086/api/interpreter?data=[out:json][timeout:5];out%20count;'
```

## Parametri (env, tutti con default in `docker-compose.yml`)

| Var | Default | Note |
|---|---|---|
| `OVERPASS_PORT` | `18086` | porta host → 80 del container |
| `OVERPASS_META` | `no` | `yes`/`attic` per tenere lo storico (DB molto più grande) |
| `OVERPASS_PLANET_URL` | Italia `.pbf` Geofabrik | per il Sud: `…/europe/italy/sud-latest.osm.pbf` |
| `OVERPASS_DIFF_URL` | Italia updates Geofabrik | per il Sud: `…/europe/italy/sud-updates/` |
| `OVERPASS_UPDATE_SLEEP` | `86400` | i diff Geofabrik sono giornalieri |
| `OVERPASS_RULES_LOAD` | `10` | parallelismo in fase di build |

## Note operative

- **Conversione `.pbf`**: l'entrypoint dell'immagine scarica sempre su
  `planet.osm.bz2`. `OVERPASS_PLANET_PREPROCESS` (impostato nel compose) converte
  il `.pbf` in `.bz2` con `osmium` (incluso nell'immagine) prima del build.
- **Aggiornamento dati**: i diff giornalieri Geofabrik mantengono il DB allineato;
  senza connettività ai diff i dati invecchiano. Un re-init periodico (cancella il
  volume e riavvia) riallinea da zero.
- **Cambio scope**: se l'app esce dalla Puglia e hai inizializzato col solo Sud,
  serve re-init con l'estratto più grande (cancella `opendata-ai-overpass-db`).
- **Produzione (VPS Aruba)**: il profilo `overpass` non è incluso nel deploy di
  default. Per attivarlo lì, aggiungi `overpass` ai `SERVICES` del workflow e
  imposta `OVERPASS_URL` nell'`.env.opendata`, verificando prima lo spazio disco.

Immagine: [`wiktorn/overpass-api`](https://github.com/wiktorn/Overpass-API).
Estratti: [Geofabrik](https://download.geofabrik.de/europe/italy.html) (ODbL).
