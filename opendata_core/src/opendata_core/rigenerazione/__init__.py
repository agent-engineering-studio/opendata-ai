"""Dimensionamento parametrico delle dotazioni urbane di rigenerazione.

Motore PURO (no FastMCP/FastAPI/LLM): dalla popolazione residente calcola i
target normativi di dotazione per quattro domini — aree mercatali/eventi, sport
e impianti sportivi, rete ciclabile/mobilità dolce, traffico/mobilità sostenibile
— secondo il framework parametrico (D.M. 1444/1968, norme CONI-CIS, riferimenti
PUMS). I coefficienti, le soglie e le classi dimensionali vivono qui; nessuna
fonte live. Sono OBIETTIVI di programmazione, non dati osservati.
"""

from .dimensionamento import DOMINI, dimensiona

__all__ = ["dimensiona", "DOMINI"]
