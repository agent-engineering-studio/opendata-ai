"""Backend del cruscotto regionale (#229, F2 di #227).

Interroga il warehouse (`ComuneAnagrafica` + ultimi `maturity_assessments`),
costruisce le sintesi-comune e le passa al motore puro `opendata_core.region`.
Espone `/regione/overview` e `/regione/comuni`, scoped su `REGION`.
"""
