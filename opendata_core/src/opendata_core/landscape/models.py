"""Modello normalizzato del vincolo paesaggistico, indipendente dalla regione (#128)."""

from __future__ import annotations

from pydantic import BaseModel


class LandscapeConstraint(BaseModel):
    """Esito dell'interrogazione puntuale del piano paesaggistico regionale.

    Normalizzato: ``reconcile_polygon`` lo consuma allo stesso modo qualunque sia
    la regione/adattatore che l'ha prodotto. ``vincolato=False`` con ``tutele=[]``
    è un esito valido ("interrogato, nessuna tutela nel punto"), distinto da
    ``None`` a monte (fonte non interrogabile → confidenza degradata)."""

    vincolato: bool
    tutele: list[str]  # nomi dei layer di tutela vincolanti intersecati nel punto
    regione: str
    source_url: str
    licenza: str
