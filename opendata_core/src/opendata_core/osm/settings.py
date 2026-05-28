"""OSM-related runtime settings — shared by every consumer of opendata-core.

Loaded once at import time from environment variables (and `.env` when present).
The MCP-transport settings (MCP_TRANSPORT/MCP_HOST/MCP_PORT) remain owned by
the `osm-mcp` server itself and are not exposed here.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class OsmSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OSM upstream endpoints (can be overridden for self-hosted deployments)
    NOMINATIM_URL: str = "https://nominatim.openstreetmap.org"
    OVERPASS_URL: str = "https://overpass-api.de/api/interpreter"
    OSRM_URL: str = "https://router.project-osrm.org"

    # Identification required by Nominatim/Overpass usage policy
    OSM_USER_AGENT: str = "opendata-core/0.1 (agent-engineering-studio)"
    OSM_CONTACT_EMAIL: str | None = None

    # Map rendering
    MAP_TILE_URL: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    MAP_ATTRIBUTION: str = (
        '&copy; <a href="https://www.openstreetmap.org/copyright">'
        "OpenStreetMap</a> contributors"
    )
    MAP_DEFAULT_ZOOM: int = 13
    MAP_MAX_FEATURES_PER_LAYER: int = 5000

    # HTTP
    HTTP_TIMEOUT: float = 30.0


osm_settings = OsmSettings()
