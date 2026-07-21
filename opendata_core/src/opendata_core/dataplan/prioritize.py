"""Prioritizzazione valore×sforzo dei dataset candidati (#173, D2 di #170).

Motore **puro e deterministico** (no LLM): dato il catalogo D1, ordina i candidati
su una matrice **valore×sforzo** con una motivazione per voce. I "quick win" (alto
valore, basso sforzo/rischio) emergono in testa.

Il **valore** combina i segnali già presenti nel progetto — appartenenza **HVD**
(Reg. UE 2023/138, come `maturity/hvd.py`), riuso reale (un dataset che *sblocca
un'analisi* pesa di più — anello valore⇄maturità), e la trasparenza dei dati già
aperti a livello nazionale. Lo **sforzo** viene dal campo `sforzo` del catalogo
corretto da privacy (`personale` → de-identificazione) e dal fatto che il dato
sia già aperto altrove (→ "solo link", sforzo minimo). Nessun punteggio è
inventato: i pesi sono espliciti e i test deterministici.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel

from .models import CandidateDataset

Quadrante = Literal["quick_win", "strategico", "riempitivo", "basso_valore"]

# ── pesi del VALORE (0..100) ────────────────────────────────────────────────
_HVD_BONUS = 40          # appartiene a una categoria HVD
_NO_HVD_BASE = 10        # non-HVD: valore di base
_SBLOCCA_EACH = 15       # per analisi/lente/use-case sbloccata (riuso reale)
_SBLOCCA_CAP = 45        # tetto al contributo del riuso
_GIA_APERTO_BONUS = 20   # dato già aperto a livello nazionale → trasparenza a costo ~0

# ── pesi dello SFORZO (1=minimo .. 4=massimo) ───────────────────────────────
_SFORZO_BASE = {"basso": 1, "medio": 2, "alto": 3}
_PRIVACY_PERSONALE_EXTRA = 1  # de-identificazione obbligatoria

# soglie della matrice
_VALORE_ALTO = 55
_SFORZO_BASSO = 1  # <=1 = basso (include "solo link")


class RankedCandidate(BaseModel):
    """Un candidato con punteggi, quadrante della matrice e motivazione."""

    candidate: CandidateDataset
    valore: int          # 0..100
    sforzo: int          # 1..4 (1 = minimo / "solo link")
    quadrante: Quadrante
    motivazione: str


def _valore(c: CandidateDataset, reuse_boost: dict[str, int] | None) -> int:
    score = _HVD_BONUS if c.hvd else _NO_HVD_BASE
    n_sblocca = len(c.sblocca) + (reuse_boost or {}).get(c.id, 0)
    score += min(n_sblocca * _SBLOCCA_EACH, _SBLOCCA_CAP)
    if c.gia_aperto is not None:
        score += _GIA_APERTO_BONUS
    return min(score, 100)


def _sforzo(c: CandidateDataset) -> int:
    if c.gia_aperto is not None:
        return 1  # non si produce nulla: si linka la fonte nazionale
    base = _SFORZO_BASE[c.sforzo]
    if c.privacy == "personale":
        base += _PRIVACY_PERSONALE_EXTRA
    return base


def _quadrante(valore: int, sforzo: int) -> Quadrante:
    alto_valore = valore >= _VALORE_ALTO
    basso_sforzo = sforzo <= _SFORZO_BASSO
    if alto_valore and basso_sforzo:
        return "quick_win"
    if alto_valore:
        return "strategico"
    if basso_sforzo:
        return "riempitivo"
    return "basso_valore"


def _motivazione(c: CandidateDataset, valore: int, sforzo: int, quad: Quadrante) -> str:
    parti: list[str] = []
    if c.gia_aperto is not None:
        parti.append(f"già aperto su {c.gia_aperto.fonte} → basta linkarlo (sforzo minimo)")
    if c.hvd:
        parti.append(f"dataset ad alto valore (HVD: {c.hvd})")
    if c.sblocca:
        parti.append(f"sblocca {len(c.sblocca)} analisi ({', '.join(c.sblocca)})")
    if c.privacy == "personale":
        parti.append("richiede de-identificazione (dati personali)")
    elif c.privacy == "aggregato":
        parti.append("pubblicabile solo in forma aggregata")
    testa = {
        "quick_win": "Quick win",
        "strategico": "Intervento strategico",
        "riempitivo": "Riempitivo (basso sforzo, valore contenuto)",
        "basso_valore": "Bassa priorità",
    }[quad]
    dettaglio = "; ".join(parti) if parti else "nessun segnale di valore particolare"
    return f"{testa}: {dettaglio}. (valore {valore}/100, sforzo {sforzo}/4)"


# ordine dei quadranti nel ranking (i quick win in testa)
_QUAD_ORDER = {"quick_win": 0, "strategico": 1, "riempitivo": 2, "basso_valore": 3}


def prioritize(
    candidates: Iterable[CandidateDataset],
    *,
    reuse_boost: dict[str, int] | None = None,
) -> list[RankedCandidate]:
    """Ordina i candidati sulla matrice valore×sforzo (quick win in testa).

    ``reuse_boost``: incremento opzionale (iniettato dal backend) del segnale di
    riuso per id candidato — es. una *domanda di riuso non soddisfatta* osservata
    nei report Territorio dà più peso a quel dataset. Deterministico: a parità di
    quadrante ordina per valore desc, sforzo asc, poi id.
    """
    ranked: list[RankedCandidate] = []
    for c in candidates:
        v = _valore(c, reuse_boost)
        s = _sforzo(c)
        # Un dato già aperto a livello nazionale è SEMPRE un quick win: zero
        # produzione (basta linkarlo) e trasparenza immediata, a prescindere
        # dall'HVD (cfr. lotto "Priorità 1" del piano dimostrativo, §D8).
        q = "quick_win" if c.gia_aperto is not None else _quadrante(v, s)
        ranked.append(RankedCandidate(
            candidate=c, valore=v, sforzo=s, quadrante=q,
            motivazione=_motivazione(c, v, s, q),
        ))
    # Ordine: quadrante (quick win in testa) → dentro i quick win prima i dati
    # "già aperti" (solo link, zero produzione: lotto Priorità 1 §D8) → poi valore
    # desc, sforzo asc, id (determinismo).
    ranked.sort(key=lambda r: (
        _QUAD_ORDER[r.quadrante],
        0 if r.candidate.gia_aperto is not None else 1,
        -r.valore, r.sforzo, r.candidate.id,
    ))
    return ranked
