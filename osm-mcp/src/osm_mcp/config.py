"""Runtime configuration for the OSM MCP server.

OSM-specific settings (NOMINATIM_URL, OVERPASS_URL, MAP_*, HTTP_TIMEOUT, ...)
live in `opendata_core.osm.settings` so the same defaults are honoured by both
this MCP wrapper and the unified backend that consumes `opendata-core`
directly. This module only owns the MCP transport knobs.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Transport
    MCP_TRANSPORT: str = "stdio"  # "stdio" | "sse" | "streamable-http"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8080


settings = Settings()
