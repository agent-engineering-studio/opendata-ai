
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
