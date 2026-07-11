"""Gate di qualità del report territoriale (`report_quality`) — motore puro.

Verifica i 5 gate auto-valutabili (Fase 1) su input sintetici e comune-agnostici:
nessun letterale di un comune specifico, solo le casistiche dei difetti ricorrenti.
"""

from __future__ import annotations

from opendata_core.report_quality import (
    gate_certificazioni,
    gate_denominatore,
    gate_dedup,
    gate_freshness,
    gate_riconciliazione_suolo,
    gate_vincoli,
    valuta_report,
)

ANNO = 2026


# ── Freshness ───────────────────────────────────────────────────────


def test_freshness_censimento_2011_fail() -> None:
    f = gate_freshness(["Secondo il Censimento 2011 la popolazione era…"], anno_corrente=ANNO)
    assert f.esito == "FAIL" and f.tipo == "critica"


def test_freshness_2011_etichettato_storico_pass() -> None:
    f = gate_freshness(
        ["Il dato storico del Censimento 2011 mostra…"], anno_corrente=ANNO
    )
    assert f.esito == "PASS"


def test_freshness_anno_vecchio_warn() -> None:
    f = gate_freshness(["Fonte: dati ISTAT 2015 sull'occupazione."], anno_corrente=ANNO)
    assert f.esito == "WARN" and "2015" in f.messaggio


def test_freshness_range_fondi_non_falsa_positivo() -> None:
    # "FESR 2021-2027" non è un'annualità di dato → nessun WARN.
    f = gate_freshness(["Linea FESR Puglia 2021-2027, dati ISTAT 2024."], anno_corrente=ANNO)
    assert f.esito == "PASS"


# ── Denominatore ────────────────────────────────────────────────────


def test_denominatore_due_popolazioni_fail() -> None:
    f = gate_denominatore(
        ["27.889 abitanti secondo una fonte", "ma 26.731 ab. secondo un'altra"],
        pop_rif=26731,
    )
    assert f.esito == "FAIL" and "27889" in f.messaggio and "26731" in f.messaggio


def test_denominatore_unico_coerente_pass() -> None:
    f = gate_denominatore(["La popolazione è di 26.731 abitanti."], pop_rif=26731)
    assert f.esito == "PASS"


def test_denominatore_diverso_dal_riferimento_warn() -> None:
    f = gate_denominatore(["27.889 residenti."], pop_rif=26731)
    assert f.esito == "WARN"


def test_denominatore_ignora_conteggi_non_popolazione() -> None:
    # "570 posti letto" / "16 attrattori": niente suffisso popolazione → ignorati.
    f = gate_denominatore(["570 posti letto e 16 attrattori; 26.731 ab."], pop_rif=26731)
    assert f.esito == "PASS"


# ── Certificazioni ──────────────────────────────────────────────────


def test_certificazioni_non_riscontrate_warn() -> None:
    f = gate_certificazioni(
        ["Il Pecorino locale DOP è un'eccellenza."], evidenze_testo="ISTAT ricettività 2024"
    )
    assert f.esito == "WARN" and "DOP" in f.messaggio


def test_certificazioni_riscontrate_pass() -> None:
    f = gate_certificazioni(
        ["Il vino locale DOC è citato."],
        evidenze_testo="Registro MASAF: vino DOC del territorio (eAmbrosia)",
    )
    assert f.esito == "PASS"


def test_certificazioni_assenti_pass() -> None:
    assert gate_certificazioni(["Nessuna certificazione qui."], evidenze_testo="").esito == "PASS"


# ── Dedup ───────────────────────────────────────────────────────────


def test_dedup_titoli_simili_warn() -> None:
    f = gate_dedup([
        "Rete ciclabile urbana per la mobilità sostenibile",
        "Mobilità sostenibile: nuova rete ciclabile urbana",
        "Sistema museale integrato",
    ])
    assert f.esito == "WARN"


def test_dedup_titoli_distinti_pass() -> None:
    f = gate_dedup([
        "Rete ciclabile urbana",
        "Sistema museale integrato",
        "Mercato coperto polifunzionale",
    ])
    assert f.esito == "PASS"


# ── Vincoli ─────────────────────────────────────────────────────────


def test_vincoli_rinviati_con_dato_disponibile_warn() -> None:
    f = gate_vincoli(
        ["L'intersezione PAI per l'area è da verificare."],
        vincolo_comunale_disponibile=True,
    )
    assert f.esito == "WARN"


def test_vincoli_rinvio_senza_dato_pass() -> None:
    # Nessun esito comunale disponibile → il rinvio è legittimo, niente WARN.
    f = gate_vincoli(
        ["L'intersezione PAI per l'area è da verificare."],
        vincolo_comunale_disponibile=False,
    )
    assert f.esito == "PASS"


# ── Aggregatore / scorecard ─────────────────────────────────────────


def test_valuta_report_pulito_pubblicabile() -> None:
    q = valuta_report(
        testi=["La popolazione è di 26.731 abitanti; dati ISTAT 2024."],
        titoli_proposte=["Rete ciclabile", "Sistema museale"],
        pop_rif=26731,
        anno_corrente=ANNO,
        evidenze_testo="ISTAT 2024",
        vincolo_comunale_disponibile=True,
    )
    assert q.esito == "PASS" and q.pubblicabile
    # 5 gate Parte IV + gate suolo (PASS con soil_records assenti) = 6 dimensioni
    assert q.punteggio == q.massimo == 12
    assert len(q.findings) == 6


def test_valuta_report_critica_blocca_pubblicazione() -> None:
    q = valuta_report(
        testi=["Censimento 2011: 27.889 abitanti, ma altrove 26.731 ab."],
        titoli_proposte=[],
        pop_rif=26731,
        anno_corrente=ANNO,
    )
    assert q.esito == "FAIL" and not q.pubblicabile
    md = q.markdown()
    assert "Qualità del report" in md and "13 dimensioni" in md
    d = q.to_dict()
    assert d["esito"] == "FAIL" and len(d["controlli"]) == 6


# ── Gate Parte V — Riconciliazione suolo (WARN, mai FAIL) ────────────


def test_gate_suolo_senza_record_pass() -> None:
    f = gate_riconciliazione_suolo(None)
    assert f.esito == "PASS" and f.tipo == "alta"


def test_gate_suolo_confidenza_bassa_warn() -> None:
    f = gate_riconciliazione_suolo([
        {"confidenza": "Bassa", "classificazione": "DISMESSO"},
        {"confidenza": "Alta", "classificazione": "VINCOLATO"},
    ])
    assert f.esito == "WARN" and f.tipo == "alta"
    assert "1/2" in f.messaggio


def test_gate_suolo_tutto_risolto_pass() -> None:
    f = gate_riconciliazione_suolo([
        {"confidenza": "Alta", "classificazione": "VINCOLATO"},
        {"confidenza": "Media", "classificazione": "DISMESSO"},
    ])
    assert f.esito == "PASS"


def test_gate_suolo_warn_non_blocca_pubblicazione() -> None:
    # anche con suolo a confidenza bassa, un report altrimenti pulito resta pubblicabile
    q = valuta_report(
        testi=["La popolazione è di 26.731 abitanti; dati ISTAT 2024."],
        titoli_proposte=["Rete ciclabile", "Sistema museale"],
        pop_rif=26731,
        anno_corrente=ANNO,
        evidenze_testo="ISTAT 2024",
        vincolo_comunale_disponibile=True,
        soil_records=[{"confidenza": "Bassa", "classificazione": "DA_VERIFICARE"}],
    )
    assert q.esito == "WARN"        # c'è un WARN...
    assert q.pubblicabile is True   # ...ma "alta" non è "critica" → non blocca
