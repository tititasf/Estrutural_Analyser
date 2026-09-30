"""Rotulo de certificacao por classe (certificado/beta) — R9 / DP-13.

O portal NAO decide certificacao; so LE o estado atual do funil do dono e exibe.
Fonte read-only: docs/STATUS.md (gerado por scripts/arete/gerar_status.py a partir
de relatorios Arete + GOLDEN + triagem + DB). Em conflito, STATUS.md vence (e' o dado).

[ASSUMPTION] STATUS.md nao imprime a palavra 'certificado'/'beta' literalmente; ele
publica, por classe+pav, a coluna "Arete %" e um "Alerta" ("FAIL aberto"). Regra
derivada, documentada e conservadora (nunca superestima certificacao):
    Arete% == 100.0 e sem "FAIL aberto"  ->  'certificado'
    qualquer outro caso                  ->  'beta'
Se STATUS.md nao existir ou a classe nao aparecer, retorna 'beta' (fail-safe: o
usuario ve o rotulo mais cauteloso, nunca 'certificado' por engano). Um mapa
PORTAL_CERT_OVERRIDE (env, "PL:certificado,FV:beta") permite o dono forcar o rotulo
sem esperar nova geracao do STATUS. Se um dia o STATUS passar a emitir o selo real,
trocar apenas o parser aqui — o resto do portal so consome classificar_certificacao().

Mapeamento de nomes de classe: a UI/assemble_n5 usa PL/LV/FV/LJ; o STATUS usa
PIL/LV/FV/LAJ. _norm_classe unifica para o vocabulario de assemble_n5.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

StatusCert = Literal["certificado", "beta"]

# STATUS (Arete) -> vocabulario de assemble_n5 (repository.CLASSES_N5)
_ALIAS = {
    "PIL": "PL",
    "PL": "PL",
    "LV": "LV",
    "FV": "FV",
    "LAJ": "LJ",
    "LJ": "LJ",
}

# linha da tabela "Ultima rodada Arete por classe":
# | Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Alerta |
_LINHA_RE = re.compile(
    r"^\|\s*(?P<classe>[A-Z]+)\s*\|"       # Classe
    r"[^|]*\|"                              # Pav
    r"[^|]*\|"                              # Run
    r"[^|]*\|"                              # PASS
    r"[^|]*\|"                              # FAIL
    r"[^|]*\|"                              # BLOCKED
    r"\s*(?P<arete>[\d.]+)%\s*\|"          # Arete %
    r"[^|]*\|"                              # Golden selado
    r"(?P<alerta>[^|]*)\|"                 # Alerta
)


def _norm_classe(classe: str) -> str | None:
    return _ALIAS.get((classe or "").strip().upper())


def _parse_overrides() -> dict[str, StatusCert]:
    """PORTAL_CERT_OVERRIDE="PL:certificado,FV:beta" -> {'PL':'certificado',...}."""
    raw = os.environ.get("PORTAL_CERT_OVERRIDE", "").strip()
    out: dict[str, StatusCert] = {}
    if not raw:
        return out
    for par in raw.split(","):
        if ":" not in par:
            continue
        cls, val = par.split(":", 1)
        cls = _norm_classe(cls)
        val = val.strip().lower()
        if cls and val in ("certificado", "beta"):
            out[cls] = val  # type: ignore[assignment]
    return out


def carregar_mapa_certificacao(status_md_path: str | Path) -> dict[str, StatusCert]:
    """Le STATUS.md (read-only) e devolve {classe_norm: 'certificado'|'beta'}.

    Uma classe e' 'certificado' apenas se TODAS as suas linhas (pavimentos) estao a
    100% sem FAIL aberto. Basta um pavimento em beta para a classe inteira ser beta —
    regra conservadora (nunca liberar rotulo forte com um pav em treino).
    """
    mapa: dict[str, StatusCert] = {}
    path = Path(status_md_path)
    if not path.exists():
        return _parse_overrides()  # sem fonte -> so overrides; resto vira beta no getter

    try:
        texto = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _parse_overrides()

    for linha in texto.splitlines():
        m = _LINHA_RE.match(linha.strip())
        if not m:
            continue
        classe = _norm_classe(m.group("classe"))
        if classe is None:
            continue
        try:
            arete = float(m.group("arete"))
        except ValueError:
            arete = 0.0
        tem_fail = "fail" in m.group("alerta").lower()
        cert = "certificado" if (arete >= 100.0 and not tem_fail) else "beta"
        # rebaixa a classe inteira se qualquer pav for beta
        if mapa.get(classe) == "beta" or cert == "beta":
            mapa[classe] = "beta"
        else:
            mapa[classe] = "certificado"

    mapa.update(_parse_overrides())  # override do dono tem a ultima palavra
    return mapa


def classificar_certificacao(status_md_path: str | Path, classe: str) -> StatusCert:
    """Rotulo de UMA classe. Fail-safe: desconhecida/ausente -> 'beta' (cauteloso, R9)."""
    norm = _norm_classe(classe)
    if norm is None:
        return "beta"
    mapa = carregar_mapa_certificacao(status_md_path)
    return mapa.get(norm, "beta")
