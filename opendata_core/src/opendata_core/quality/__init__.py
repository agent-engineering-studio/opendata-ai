"""Data Quality Lab — motori puri di diagnosi/qualità di un dato (Punto 01 roadmap).

Niente FastMCP/FastAPI/LLM: solo analisi deterministica. `profile_csv` ispeziona
un CSV e restituisce un report (profilo colonne, problemi, punteggio) riusabile
dal backend (endpoint), da una skill A2A e dalla UI.
"""

from .dcat import generate_dcat
from .dcat_validate import validate_dcat
from .enrich import advise_enrichment
from .fix import fix_csv
from .geo import profile_geojson
from .geoconvert import csv_to_geojson, json_to_geojson
from .geoschema import infer_geo_schema
from .normalize import build_normalization
from .package import build_publish_package
from .parquet import csv_to_parquet
from .profile import profile_csv
from .scale import advise_scale
from .schema import infer_schema
from .schemaorg import generate_schema_org
from .schemaorg_validate import validate_schema_org
from .summarize import summarize_csv

__all__ = [
    "profile_csv", "fix_csv", "profile_geojson", "generate_dcat", "validate_dcat",
    "infer_schema", "csv_to_geojson", "json_to_geojson", "summarize_csv", "advise_scale",
    "build_publish_package", "advise_enrichment", "build_normalization", "infer_geo_schema",
    "generate_schema_org", "validate_schema_org", "csv_to_parquet",
]
