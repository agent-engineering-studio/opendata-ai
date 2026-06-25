"""Dimensionamento parametrico delle dotazioni urbane di rigenerazione.

Motore PURO (no FastMCP/FastAPI/LLM): valuta un CATALOGO di "pattern" — iniettato
dal chiamante — calcolando i target normativi di dotazione a partire dalla
popolazione residente. Ogni idea-di-sviluppo (aree mercatali, sport, ciclabili,
mobilità, parcheggi…) è un record dati eseguito in modo uniforme: aggiungerne uno
è una riga di catalogo (vedi `opendata_backend/config_data/rigenerazione_patterns.yaml`),
non codice. I valori sono OBIETTIVI di programmazione, non dati osservati.
"""

from .dimensionamento import valuta_pattern
from .scoring import SOGLIA_IDONEITA, score_candidato, valuta_aree

__all__ = ["valuta_pattern", "score_candidato", "valuta_aree", "SOGLIA_IDONEITA"]
