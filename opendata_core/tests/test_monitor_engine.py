"""Test del motore di monitoraggio — freshness/qualità/link + diff (#88)."""

from __future__ import annotations

from opendata_core.monitor import check_freshness, check_links, check_quality_regression, diff_runs, run_checks


# ── freshness ────────────────────────────────────────────────────────────
def test_freshness_stantio_livello_alto() -> None:
    f = check_freshness("MONTHLY", "2024-01-01T00:00:00", "2026-01-01T00:00:00")
    assert f is not None
    assert f["livello"] == "alto"
    assert f["codice"] == "stantio"


def test_freshness_entro_tolleranza_nessun_finding() -> None:
    assert check_freshness("MONTHLY", "2026-06-20T00:00:00", "2026-07-06T00:00:00") is None


def test_freshness_senza_periodicita_non_giudicabile() -> None:
    assert check_freshness(None, "2020-01-01T00:00:00", "2026-01-01T00:00:00") is None
    assert check_freshness("IRREGULAR", "2020-01-01T00:00:00", "2026-01-01T00:00:00") is None


def test_freshness_senza_data_non_giudicabile() -> None:
    assert check_freshness("MONTHLY", None, "2026-01-01T00:00:00") is None


# ── regressione qualità ──────────────────────────────────────────────────
def test_regressione_qualita_rilevata() -> None:
    f = check_quality_regression(65, 90)
    assert f is not None
    assert f["livello"] == "medio"


def test_regressione_qualita_grave_livello_alto() -> None:
    f = check_quality_regression(40, 90)
    assert f["livello"] == "alto"


def test_nessuna_regressione_se_migliora_o_stabile() -> None:
    assert check_quality_regression(95, 90) is None
    assert check_quality_regression(85, 90) is None  # sotto soglia (10 punti)


def test_nessun_run_precedente_nessun_giudizio() -> None:
    assert check_quality_regression(30, None) is None


# ── link ─────────────────────────────────────────────────────────────────
def test_link_rotto_404() -> None:
    findings = check_links([{"url": "https://x.it/a.csv", "status_code": 404}])
    assert len(findings) == 1
    assert findings[0]["codice"] == "link_rotto" and findings[0]["livello"] == "alto"


def test_link_irraggiungibile() -> None:
    findings = check_links([{"url": "https://x.it/a.csv", "errore": "timeout"}])
    assert findings[0]["codice"] == "link_irraggiungibile"


def test_link_ok_nessun_finding() -> None:
    assert check_links([{"url": "https://x.it/a.csv", "status_code": 200}]) == []


# ── run_checks + diff ──────────────────────────────────────────────────
def test_run_checks_esito_ok_senza_problemi() -> None:
    r = run_checks(
        periodicita=None, ultimo_aggiornamento_iso=None, ora_iso="2026-01-01T00:00:00",
        punteggio_attuale=90, punteggio_precedente=90, link_risultati=[{"url": "x", "status_code": 200}],
    )
    assert r == {"findings": [], "esito": "ok"}


def test_run_checks_esito_critico_con_link_rotto() -> None:
    r = run_checks(
        periodicita=None, ultimo_aggiornamento_iso=None, ora_iso="2026-01-01T00:00:00",
        punteggio_attuale=None, punteggio_precedente=None,
        link_risultati=[{"url": "x", "status_code": 404}],
    )
    assert r["esito"] == "critico"
    assert len(r["findings"]) == 1


def test_diff_runs_nuovi_risolti_invariati() -> None:
    precedenti = [{"livello": "alto", "codice": "link_rotto", "messaggio": "x"}]
    attuali = [
        {"livello": "alto", "codice": "link_rotto", "messaggio": "x"},
        {"livello": "medio", "codice": "stantio", "messaggio": "y"},
    ]
    d = diff_runs(precedenti, attuali)
    assert d["invariati"] == ["link_rotto"]
    assert [f["codice"] for f in d["nuovi"]] == ["stantio"]
    assert d["risolti"] == []


def test_diff_runs_senza_precedente_tutto_nuovo() -> None:
    attuali = [{"livello": "alto", "codice": "link_rotto", "messaggio": "x"}]
    d = diff_runs(None, attuali)
    assert [f["codice"] for f in d["nuovi"]] == ["link_rotto"]
    assert d["risolti"] == []


def test_diff_runs_tutto_risolto() -> None:
    precedenti = [{"livello": "alto", "codice": "link_rotto", "messaggio": "x"}]
    d = diff_runs(precedenti, [])
    assert d["risolti"] == ["link_rotto"]
    assert d["nuovi"] == []
