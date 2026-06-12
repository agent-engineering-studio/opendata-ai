"""Mapping reale dell'API IdroGEO (ISPRA), da discovery 2026-06-12.

Endpoint verificato: ``https://idrogeo.isprambiente.it/api/pir/comuni/{uid}``
(PIR = Piattaforma IdroGEO Rischio). Comportamenti osservati:
  - ``uid`` è il codice ISTAT del comune; accetta sia la forma zero-padded
    ("072006") sia l'intero (72006) — risposta identica;
  - JSON piatto con 134 chiavi: aree/percentuali per classe di pericolosità
    e popolazione/famiglie/edifici/imprese/beni culturali esposti;
  - frane (IFFI/PAI): classi P4 (molto elevata), P3 (elevata), P2, P1, AA
    (aree di attenzione) + aggregato P3+P4; prefissi ``ar_fr``/``pop_fr``/
    ``fam_fr``/``ed_fr``/``im_fr``/``bbcc_fr``, percentuali con suffisso ``_p``;
  - idraulica (alluvioni, D.Lgs. 49/2010): P3 (elevata/HPH), P2 (media/MPH),
    P1 (bassa/LPH); prefissi ``ar_id``/``pop_idr``/``fam_idr``/``ed_idr``/
    ``im_idr``/``bbcc_id``;
  - contesto: ``nome``, ``ar_kmq``, ``pop_res011``/``pop_res021`` (censimenti),
    ``extent`` (bbox).

NOTA discovery (divergenza dalla spec 07): il **consumo di suolo** ISPRA non
espone alcuna API REST utilizzabile (solo tabelle comunali XLSX annuali e
servizi cartografici) → fuori scope del client; parte dei dataset è comunque
raggiungibile via CKAN (dati.gov.it).

Licenza dati: CC BY-SA 3.0 IT — citazione ISPRA obbligatoria negli output.
"""

from __future__ import annotations

LICENZA = "ISPRA IdroGEO — CC BY-SA 3.0 IT"

#: Classi di pericolosità da frana, dalla più severa.
FRANE_CLASSI = ("p4", "p3", "p2", "p1", "aa")
#: Classi di pericolosità idraulica.
IDRAULICA_CLASSI = ("p3", "p2", "p1")

#: classe → (chiave_api_area_kmq, chiave_api_pct). Nomi verificati sul JSON
#: reale: l'area pct è ``ar_fr<classe>_p`` tranne l'aggregato ``ar_frp3p4p``.
FRANE_AREA_KEYS = {
    **{c: (f"ar_fr_{c}", f"ar_fr{c}_p") for c in FRANE_CLASSI},
    "p3p4": ("ar_fr_p3p4", "ar_frp3p4p"),
}
FRANE_POP_KEYS = {c: (f"pop_fr_{c}", f"popfr{c}_p") for c in FRANE_CLASSI}
IDRAULICA_AREA_KEYS = {c: (f"ar_id_{c}", f"arid{c}_p") for c in IDRAULICA_CLASSI}
IDRAULICA_POP_KEYS = {c: (f"pop_idr_{c}", f"popid{c}_p") for c in IDRAULICA_CLASSI}


def comune_uid(cod_comune: str | int) -> int:
    """Codice ISTAT (anche zero-padded) → uid IdroGEO (intero)."""
    try:
        return int(str(cod_comune).strip())
    except ValueError as exc:
        raise ValueError(
            f"Codice comune ISTAT {cod_comune!r} non valido: atteso numerico (es. '072006')."
        ) from exc
