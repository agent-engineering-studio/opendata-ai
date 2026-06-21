"""Data Quality Lab — motori puri di diagnosi/qualità di un dato (Punto 01 roadmap).

Niente FastMCP/FastAPI/LLM: solo analisi deterministica. `profile_csv` ispeziona
un CSV e restituisce un report (profilo colonne, problemi, punteggio) riusabile
dal backend (endpoint), da una skill A2A e dalla UI.
"""

from .profile import profile_csv

__all__ = ["profile_csv"]
