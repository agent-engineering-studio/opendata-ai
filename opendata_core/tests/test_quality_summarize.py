"""Test dei riepiloghi pronti da CSV (Data Quality Lab / Punto 03 #51)."""

from __future__ import annotations

from opendata_core.quality import summarize_csv


def test_numeric_categorie_serie() -> None:
    csv = (
        "comune;provincia;popolazione;anno\n"
        "Bari;BA;320.000;2021\n"
        "Monopoli;BA;49.000;2021\n"
        "Lecce;LE;95.000;2022\n"
        "Galatina;LE;27.000;2022\n"
    )
    s = summarize_csv(csv)
    assert s["righe"] == 4

    # numerica: popolazione con migliaia all'italiana normalizzate
    pop = next(n for n in s["numeric"] if n["column"] == "popolazione")
    assert pop["somma"] == 491000.0
    assert pop["max"] == 320000.0
    assert pop["conteggio"] == 4

    # categoria: provincia a bassa cardinalità → totali per valore
    prov = next(c for c in s["categorie"] if c["column"] == "provincia")
    assert prov["distinti"] == 2
    top = {t["valore"]: t["conteggio"] for t in prov["top"]}
    assert top == {"BA": 2, "LE": 2}
    assert prov["top"][0]["quota_pct"] == 50.0

    # serie temporale: anni
    anno = next(t for t in s["serie_temporali"] if t["column"] == "anno")
    assert anno["periodo"] == "anno"
    punti = {p["periodo"]: p["conteggio"] for p in anno["punti"]}
    assert punti == {"2021": 2, "2022": 2}


def test_serie_da_date_iso_e_ggmmaaaa() -> None:
    csv = "data;evento\n2020-05-01;a\n01/06/2021;b\n2021-07-10;c\n"
    s = summarize_csv(csv)
    serie = next(t for t in s["serie_temporali"] if t["column"] == "data")
    punti = {p["periodo"]: p["conteggio"] for p in serie["punti"]}
    assert punti == {"2020": 1, "2021": 2}


def test_alta_cardinalita_non_e_categoria() -> None:
    # una colonna chiave (tutti distinti) non diventa "categoria"
    csv = "id;valore\n" + "".join(f"{i};{i*2}\n" for i in range(60))
    s = summarize_csv(csv)
    assert not any(c["column"] == "id" for c in s["categorie"])


def test_vuoto_e_senza_riepiloghi() -> None:
    assert summarize_csv("")["righe"] == 0
    s = summarize_csv("a\nx\n")  # una sola colonna, un solo valore → nessun riepilogo
    assert s["numeric"] == [] and s["serie_temporali"] == []
    assert any("Nessun riepilogo" in n for n in s["note"])
