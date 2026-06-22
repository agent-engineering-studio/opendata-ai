"""A2A AgentCard for the opendata-ai orchestrator.

Six skills published — they all reuse existing machinery (`run_streaming` for
search/geo, `classify_dataset` for classify, `run_assessment` for maturity,
`run_programma` for territory, the pure `opendata_core.quality` engines for
data_quality), so the contract on the A2A side stays a thin descriptor layer
(R13: skills delegate, no duplicated logic).
"""

from __future__ import annotations

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

# Skill IDs are stable string identifiers — clients select a skill by ID via
# the `metadata.skill` field on the incoming A2A message. Keep them stable;
# renames are a breaking change.
SKILL_SEARCH = "search_open_data"
SKILL_GEO = "find_geo_resources"
SKILL_CLASSIFY = "classify_dataset"
SKILL_MATURITY = "assess_maturity"
SKILL_TERRITORY = "analyze_territory"
SKILL_QUALITY = "data_quality"


def _skills() -> list[AgentSkill]:
    return [
        AgentSkill(
            id=SKILL_SEARCH,
            name="Cerca dataset open data",
            description=(
                "Interroga in parallelo CKAN (portali open-data italiani / "
                "europei) e le fonti SDMX (ISTAT, Eurostat, OECD) e produce "
                "una sintesi narrativa + la lista delle risorse trovate."
            ),
            input_modes=["text/plain"],
            output_modes=["text/plain", "application/json"],
            tags=["opendata", "ckan", "istat", "sdmx", "italy", "eu"],
            examples=[
                "popolazione di Milano per età",
                "qualità dell'aria nelle città italiane",
                "tasso di disoccupazione regionale 2023",
            ],
        ),
        AgentSkill(
            id=SKILL_GEO,
            name="Trova risorse geografiche",
            description=(
                "Come search_open_data ma forza il bias geo (prefer_geo=true) e "
                "restituisce solo risorse mappabili (GeoJSON, Shapefile, KML, "
                "GPX, WMS), pronte per essere disegnate su una mappa."
            ),
            input_modes=["text/plain"],
            output_modes=["text/plain", "application/json"],
            tags=["opendata", "geo", "geojson", "shapefile", "wms"],
            examples=[
                "piste ciclabili di Bologna",
                "confini delle regioni italiane",
                "aree naturali protette in Lombardia",
            ],
        ),
        AgentSkill(
            id=SKILL_CLASSIFY,
            name="Classifica un dataset",
            description=(
                "Dato un dataset (source + id + nome + descrizione) e una "
                "tassonomia, ritorna i punteggi di rilevanza per ciascuna "
                "categoria. Cache 24h (Redis + Postgres)."
            ),
            input_modes=["application/json"],
            output_modes=["application/json"],
            tags=["classification", "taxonomy"],
            examples=[
                '{"source":"ckan","dataset_id":"…","dataset_name":"…","taxonomy":["sanità","mobilità"]}',
            ],
        ),
        AgentSkill(
            id=SKILL_MATURITY,
            name="Valuta la maturità open data di un ente",
            description=(
                "Dato un ente (nome / organizzazione CKAN, opz. codice ISTAT del "
                "comune) calcola la scorecard di maturità ODM 2025: 4 dimensioni "
                "(policy, portale, qualità, impatto), livello, raccomandazioni e "
                "leve di miglioramento. Per gli enti senza dati propone una guida."
            ),
            input_modes=["text/plain", "application/json"],
            output_modes=["application/json"],
            tags=["maturity", "odm", "scorecard", "italy"],
            examples=[
                "Comune di Bari",
                '{"entity":"Comune di Gioia del Colle","istat_code":"072021"}',
            ],
        ),
        AgentSkill(
            id=SKILL_QUALITY,
            name="Diagnosi e preparazione di un dato (Data Quality Lab)",
            description=(
                "Dato un file inline (CSV o GeoJSON in `content`) esegue un'azione del "
                "Data Quality Lab, scelta con `azione`: profile (diagnosi, default), fix "
                "(CSV corretto), schema (CREATE TABLE), summary (riepiloghi), scale "
                "(consigli per dataset grandi), to-geojson (tabella→mappa), validate "
                "(DCAT-AP_IT + FAIR + licenza), package (publish-assistant: dato pulito + "
                "metadati + licenza + README). Deterministico, nessun LLM."
            ),
            input_modes=["application/json"],
            output_modes=["application/json"],
            tags=["quality", "dcat-ap_it", "fair", "csv", "geojson", "publish"],
            examples=[
                '{"azione":"profile","content":"comune,popolazione\\nBari,320475\\n"}',
                '{"azione":"validate","content":"...","licenza":"CC-BY-4.0","titolo":"…"}',
                '{"azione":"package","content":"...","licenza":"CC-BY-4.0","ente":"…"}',
            ],
        ),
        AgentSkill(
            id=SKILL_TERRITORY,
            name="Analizza un territorio (SWOT + proposte)",
            description=(
                "Dato un comune (codice ISTAT) produce la scheda programmatica "
                "verificabile: sintesi, SWOT e proposte/idee con citazioni "
                "risolvibili, dal fan-out multi-fonte (ISTAT, OpenCoesione, OSM, "
                "ISPRA, …). Modalità: scheda | idee | completa | marketing."
            ),
            input_modes=["application/json"],
            output_modes=["application/json"],
            tags=["territory", "swot", "opencoesione", "programma", "italy"],
            examples=[
                '{"cod_comune":"072021","comune_nome":"Gioia del Colle","modalita":"idee"}',
            ],
        ),
    ]


def build_agent_card(public_url: str, version: str = "0.1.0") -> AgentCard:
    """Construct the AgentCard published at /.well-known/agent-card.json.

    `public_url` must be the externally reachable URL of this backend (e.g.
    `https://api.opendata.example.com` in prod, `http://localhost:18000` in dev).
    """
    return AgentCard(
        name="opendata-ai",
        description=(
            "Italian + European open-data orchestrator. Multi-source fan-out "
            "across CKAN (dati.gov.it and similar) and SDMX 2.1 endpoints "
            "(ISTAT, Eurostat, OECD), with geo resource conversion via OSM."
        ),
        version=version,
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["text/plain", "application/json"],
        capabilities=AgentCapabilities(
            streaming=True,
            extended_agent_card=False,
        ),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=f"{public_url.rstrip('/')}/a2a/",
            ),
        ],
        skills=_skills(),
    )
