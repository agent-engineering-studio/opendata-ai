"""Parser GTFS minimale: estrae le fermate (stops.txt) per popolare mobility_node."""

from .parser import GtfsStop, parse_stops, fetch_stops

__all__ = ["GtfsStop", "parse_stops", "fetch_stops"]
