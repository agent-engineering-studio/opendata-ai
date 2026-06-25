"""Motore generico di dimensionamento parametrico ("pattern" di rigenerazione).

PURO (no FastMCP/FastAPI/LLM, nessuna fonte live, nessun I/O): valuta un
CATALOGO di pattern — iniettato dal chiamante (il backend lo carica da
`config_data/rigenerazione_patterns.yaml`) — calcolando, per ciascuno, il TARGET
di dotazione a partire dalla popolazione. È il principio del documento "Territorio
in dati": ogni idea-di-sviluppo è un record dati (pattern) eseguito in modo
uniforme; aggiungere un pattern è una riga di catalogo, non codice.

I valori sono OBIETTIVI di programmazione (`Gap = Pop × indicatore − dotazione`),
NON misure osservate.

Tipi di formula supportati (`formula.tipo`):
  - `lineare`    : target = round100(pop × coeff)                  [unita mq, …]
  - `per_mille`  : target = round(pop / 1000 × coeff, decimali)    [es. km]
  - `classi`     : coeff variabile per classe dimensionale (+ assetto, soglia,
                   derivati come i posteggi = target × fattore)
  - `soglia`     : booleano pop ≥ soglia_ab → valore `se_sopra`/`se_sotto`
"""

from __future__ import annotations

from typing import Any


def _round100(x: float) -> int:
    """Arrotonda a 100 (i target sono indicativi)."""
    return int(round(x / 100.0) * 100)


def _classe(pop: int, classi: list[dict[str, Any]]) -> dict[str, Any]:
    """Prima classe la cui soglia `max_ab` non è ancora superata (None = ultima)."""
    for c in classi:
        m = c.get("max_ab")
        if m is None or pop < m:
            return c
    return classi[-1]


def _valuta_uno(pop: int, pattern: dict[str, Any]) -> dict[str, Any] | None:
    f = pattern.get("formula") or {}
    tipo = f.get("tipo")
    res: dict[str, Any] = {
        "id": pattern.get("id"),
        "tema": pattern.get("tema"),
        "indicatore": pattern.get("indicatore"),
        "unita": f.get("unita"),
        "norma": pattern.get("norma"),
        "sdg": pattern.get("sdg"),
        "geometria": pattern.get("geometria"),
        "fonti": pattern.get("fonti") or [],
        "criteri_pesi": pattern.get("criteri_pesi") or {},
        "strumenti": pattern.get("strumenti") or [],
    }
    if tipo == "lineare":
        res["target"] = _round100(pop * float(f["coeff"]))
    elif tipo == "per_mille":
        res["target"] = round(pop / 1000.0 * float(f["coeff"]), int(f.get("decimali", 1)))
    elif tipo == "classi":
        c = _classe(pop, f.get("classi") or [])
        res["assetto"] = c.get("assetto")
        res["coeff"] = c.get("coeff")
        if c.get("coeff") is None:
            res["target"] = c.get("valore_soglia")
        else:
            res["target"] = _round100(pop * float(c["coeff"]))
        for d in f.get("derivati") or []:
            try:
                res[d["nome"]] = int(round(float(res["target"]) * float(d["fattore"])))
            except (TypeError, ValueError):
                continue
    elif tipo == "soglia":
        attiva = pop >= int(f["soglia_ab"])
        res["soglia_superata"] = attiva
        res["target"] = f.get("se_sopra") if attiva else f.get("se_sotto")
    else:
        return None  # tipo sconosciuto → salta (robusto verso cataloghi futuri)
    return res


def valuta_pattern(popolazione: int, patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Valuta il catalogo `patterns` sulla popolazione, restituendo per ciascun
    pattern il target calcolato + i metadati dichiarativi (norma, fonti, geometria,
    criteri_pesi, strumenti). I pattern con `formula.tipo` sconosciuto sono saltati.
    """
    pop = max(0, int(popolazione))
    out: list[dict[str, Any]] = []
    for p in patterns or []:
        r = _valuta_uno(pop, p)
        if r is not None:
            out.append(r)
    return out
