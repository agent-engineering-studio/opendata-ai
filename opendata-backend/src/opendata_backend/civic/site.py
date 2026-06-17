"""Generatore del sito civico statico (Jinja2) — self-contained, multi-pagina.

Da uno snapshot civico (+ diff opzionale + scorecard maturità) produce un bundle di
pagine HTML self-contained: grafici SVG inline, mappa Leaflet da CDN. Ogni pagina
riporta snapshot_id/data/sources_version/kpi_version (riproducibilità) e linka le
fonti+licenza (neutralità). Linguaggio descrittivo, non politico.
"""

from __future__ import annotations

import html
import io
import zipfile
from typing import Any

from jinja2 import Environment, select_autoescape

_env = Environment(autoescape=select_autoescape(["html"]))

_CSS = """
:root{--p:#1e3a5f;--a:#2563eb;--ok:#059669;--warn:#d97706;--bad:#dc2626;--mut:#64748b}
*{box-sizing:border-box}body{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:0;color:#1e293b;background:#f8fafc}
header{background:var(--p);color:#fff;padding:14px 20px}header h1{margin:0;font-size:18px}
nav{background:#fff;border-bottom:1px solid #e2e8f0;padding:8px 20px;display:flex;flex-wrap:wrap;gap:14px}
nav a{color:var(--a);text-decoration:none;font-size:14px}main{max-width:900px;margin:0 auto;padding:20px}
h2{font-size:22px}.kpi{display:inline-block;border:1px solid #e2e8f0;border-radius:8px;padding:12px;margin:6px;min-width:150px;background:#fff}
.kpi .v{font-size:24px;font-weight:700}.kpi .l{font-size:12px;color:var(--mut)}
.src{font-size:12px;color:var(--mut)}.src a{color:var(--a)}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #e2e8f0;padding:6px;text-align:left}
.badge{border-radius:10px;padding:1px 8px;color:#fff;font-size:12px}
footer{max-width:900px;margin:0 auto;padding:16px 20px;color:var(--mut);font-size:12px;border-top:1px solid #e2e8f0}
#map{height:320px;border:1px solid #e2e8f0;border-radius:8px}
"""

_PAGES = [
    ("index.html", "Stato dell'arte"),
    ("investimenti.html", "Investimenti"),
    ("opportunita.html", "Opportunità"),
    ("rischi.html", "Rischi"),
    ("avanzamento.html", "Avanzamento"),
    ("community.html", "Community"),
]

_BASE = _env.from_string("""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ comune }} — {{ page_title }}</title><link rel="stylesheet" href="style.css">
{% if leaflet %}<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">{% endif %}</head>
<body>
<header><h1>Sito civico · {{ comune }}</h1></header>
<nav>{% for f,t in pages %}<a href="{{ f }}">{{ t }}</a>{% endfor %}
<a href="scorecard.html">Maturità</a></nav>
<main>{{ body }}</main>
<footer>
Snapshot <strong>{{ snapshot_id }}</strong> · generato il {{ created_at }} ·
versione fonti {{ sources_version }} · versione KPI {{ kpi_version }}.<br>
Dati neutrali e riproducibili. Ogni numero è tracciabile alla fonte e alla licenza indicata.
</footer>
{% if leaflet %}<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>{{ map_script|safe }}{% endif %}
</body></html>
""")


def _esc(v: Any) -> str:
    return html.escape(str(v if v is not None else "—"))


def _svg_bars(pairs: list[tuple[str, float]], *, width: int = 520, unit: str = "") -> str:
    """Grafico a barre orizzontale come SVG inline (nessuna dipendenza)."""
    if not pairs:
        return '<p class="src">Nessun dato.</p>'
    vmax = max((v for _, v in pairs), default=1) or 1
    row_h, pad = 26, 150
    height = row_h * len(pairs) + 10
    bars = []
    for i, (label, val) in enumerate(pairs):
        y = i * row_h + 8
        w = int((width - pad - 60) * (val / vmax))
        bars.append(
            f'<text x="0" y="{y+13}" font-size="11">{_esc(label)[:24]}</text>'
            f'<rect x="{pad}" y="{y+2}" width="{max(2,w)}" height="16" fill="#2563eb" rx="3"/>'
            f'<text x="{pad+max(2,w)+4}" y="{y+13}" font-size="11">{_esc(round(val,1))}{_esc(unit)}</text>'
        )
    return f'<svg width="{width}" height="{height}" role="img">{"".join(bars)}</svg>'


def _kpi_cards(kpis: dict[str, Any]) -> str:
    cards = []
    for k in kpis.values():
        val = k.get("value")
        cards.append(
            f'<div class="kpi"><div class="v">{_esc(val)}{_esc(k.get("unit") or "")}</div>'
            f'<div class="l">{_esc(k.get("label"))}</div>'
            f'<div class="src" title="{_esc(k.get("definition"))}">fonte: {_esc(k.get("source"))}</div></div>'
        )
    return "".join(cards)


def _render(page_file: str, page_title: str, body: str, ctx: dict[str, Any],
            *, leaflet: bool = False, map_script: str = "") -> str:
    return _BASE.render(
        comune=ctx["comune"], page_title=page_title, pages=_PAGES, body=body,
        snapshot_id=ctx["snapshot_id"], created_at=ctx["created_at"],
        sources_version=ctx["sources_version"], kpi_version=ctx["kpi_version"],
        leaflet=leaflet, map_script=map_script,
    )


def generate_site(
    snapshot: dict[str, Any], *, diff: dict[str, Any] | None = None,
    maturity: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Genera tutte le pagine del sito civico. Ritorna {filename: html}."""
    state = snapshot.get("payload") or {}
    kpis = snapshot.get("kpi") or {}
    report = state.get("report") or {}
    sezioni = report.get("sezioni") or {}
    center = state.get("center") or (report.get("center") if report else None)
    ctx = {
        "comune": state.get("name") or snapshot.get("istat_code"),
        "snapshot_id": snapshot.get("snapshot_id"),
        "created_at": snapshot.get("created_at"),
        "sources_version": snapshot.get("sources_version"),
        "kpi_version": snapshot.get("kpi_version"),
    }
    files: dict[str, str] = {"style.css": _CSS}

    # Stato dell'arte
    body = (
        f"<h2>Stato dell'arte</h2><p>Popolazione residente: <strong>{_esc(state.get('population'))}</strong> "
        f"(fonte ISTAT, CC BY 4.0).</p><div>{_kpi_cards(kpis)}</div>"
    )
    files["index.html"] = _render("index.html", "Stato dell'arte", body, ctx)

    # Investimenti
    inv = state.get("investimenti") or {}
    per_tema = [(t["tema"], float(t["finanziamento"])) for t in inv.get("per_tema", [])][:8]
    rows = "".join(
        f"<tr><td>{_esc(p.get('titolo'))}</td><td>{_esc(p.get('tema'))}</td><td>{_esc(p.get('stato'))}</td></tr>"
        for p in (state.get("projects") or [])[:30]
    )
    body = (
        f"<h2>Investimenti pubblici</h2><p class='src'>Fonte: OpenCoesione — "
        f"<a href='https://opencoesione.gov.it'>opencoesione.gov.it</a> (CC BY 4.0).</p>"
        f"<p>{_esc(inv.get('n_progetti'))} progetti · finanziamento totale € {_esc(inv.get('finanziamento_totale'))}.</p>"
        f"{_svg_bars(per_tema, unit=' €')}"
        f"<h3>Progetti</h3><table><tr><th>Titolo</th><th>Tema</th><th>Stato</th></tr>{rows}</table>"
    )
    files["investimenti.html"] = _render("investimenti.html", "Investimenti", body, ctx)

    # Opportunità (idee dal report → ApriQui)
    idee = sezioni.get("idee_sviluppo") or []
    items = "".join(f"<li>{_esc(i.get('category'))} — score {_esc(i.get('score'))} ({_esc(i.get('rationale'))})</li>" for i in idee)
    body = (
        f"<h2>Opportunità di sviluppo</h2><p class='src'>Derivate dall'analisi ApriQui (POI OSM, ODbL).</p>"
        f"<ul>{items or '<li>Nessuna opportunità calcolata.</li>'}</ul>"
    )
    files["opportunita.html"] = _render("opportunita.html", "Opportunità", body, ctx)

    # Rischi (gap di dato)
    gap = sezioni.get("gap_dato") or []
    body = (
        "<h2>Rischi e gap di dato</h2><p>Limiti di copertura informativa rilevati (descrittivo):</p>"
        f"<ul>{''.join(f'<li>{_esc(g)}</li>' for g in gap) or '<li>Nessun gap rilevante.</li>'}</ul>"
    )
    files["rischi.html"] = _render("rischi.html", "Rischi", body, ctx)

    # Avanzamento (diff fra snapshot, se fornito)
    if diff:
        s = diff["summary"]
        kpi_rows = "".join(
            f"<tr><td>{_esc(r['label'])}</td><td>{_esc(r['da'])}</td><td>{_esc(r['a'])}</td><td>{_esc(r['esito'])}</td></tr>"
            for r in diff["kpi"]
        )
        fatte = "".join(f"<li>{_esc(o.get('titolo') or o.get('clp'))}</li>" for o in diff["opere"]["fatte"])
        body = (
            f"<h2>Avanzamento</h2><p>{_esc(s['opere_concluse'])} opere concluse, {_esc(s['opere_nuove'])} nuove; "
            f"{_esc(s['kpi_migliorati'])} KPI migliorati, {_esc(s['kpi_peggiorati'])} peggiorati.</p>"
            f"<h3>Opere concluse</h3><ul>{fatte or '<li>—</li>'}</ul>"
            f"<h3>KPI</h3><table><tr><th>KPI</th><th>Prima</th><th>Dopo</th><th>Esito</th></tr>{kpi_rows}</table>"
        )
    else:
        body = "<h2>Avanzamento</h2><p>Disponibile dal secondo snapshot in poi (confronto periodico).</p>"
    files["avanzamento.html"] = _render("avanzamento.html", "Avanzamento", body, ctx)

    # Community
    body = (
        "<h2>Community</h2><p>Questo sito è aperto alla revisione dei cittadini. Le discussioni "
        "per tema, opera e KPI sono gestite dal servizio community (identità tramite Clerk, ruoli "
        "cittadino/amministratore/moderatore). Ad ogni nuovo snapshot viene aperto un thread di "
        "revisione \"cosa è cambiato\".</p>"
    )
    files["community.html"] = _render("community.html", "Community", body, ctx)

    # Mappa (Leaflet CDN) — pagina dedicata se c'è il centroide
    if center and center.get("lat") is not None:
        lat, lon = center["lat"], center["lon"]
        map_script = (
            f"<script>const m=L.map('map').setView([{lat},{lon}],13);"
            "L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',"
            "{attribution:'© OpenStreetMap'}).addTo(m);"
            f"L.marker([{lat},{lon}]).addTo(m);</script>"
        )
        body = "<h2>Mappa del territorio</h2><div id='map'></div>"
        files["mappa.html"] = _render("mappa.html", "Mappa", body, ctx, leaflet=True, map_script=map_script)

    # Scorecard maturità (anello valore⇄maturità)
    if maturity:
        dims = maturity.get("dimensions") or {}
        body = (
            f"<h2>Maturità open-data dell'ente</h2><p>Livello: <strong>{_esc(maturity.get('level'))}</strong> "
            f"({_esc(maturity.get('overall'))}/100).</p>"
            f"{_svg_bars([(k.title(), float(v)) for k, v in dims.items()], unit='/100')}"
        )
    else:
        body = "<h2>Maturità open-data dell'ente</h2><p>Scorecard non disponibile per questo comune.</p>"
    files["scorecard.html"] = _render("scorecard.html", "Maturità", body, ctx)

    return files


def bundle_zip(files: dict[str, str]) -> bytes:
    """Impacchetta le pagine in uno zip pubblicabile."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()
